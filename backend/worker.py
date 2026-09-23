from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def _configure_stdio() -> None:
    """Force UTF-8 on stdio so JSON commands from Electron (written as UTF-8)
    decode correctly on Windows where the default console encoding is GBK."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


_configure_stdio()


def emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


@dataclass(frozen=True)
class Note:
    onset: float
    offset: float
    pitch: int
    instrument: str
    program: int
    is_drum: bool


def representative_program(name: str) -> tuple[int, bool]:
    from muscriptor.tokenizer.mt3 import MT3_FULL_PLUS_GROUP_NAMES, MT3Tokenizer

    if name == "drums":
        return 0, True
    group_id = MT3_FULL_PLUS_GROUP_NAMES.get(name)
    if group_id is None:
        return 0, False
    tokenizer = MT3Tokenizer(instrument_vocabulary="MT3_FULL_PLUS", max_shift_steps=1001)
    programs = tokenizer.group_program_map.get(group_id, [0])
    return int(programs[0] if programs else 0), False


def load_model(model_path: Path, config_path: Path, requested_device: str, task_id: str):
    import torch
    from safetensors.torch import load_file
    from muscriptor.transcription_model import (
        TranscriptionModel,
        _build_model,
        _config_from_json,
        _remap_single_codebook_keys,
    )
    from muscriptor.tokenizer.mt3 import MT3Tokenizer

    if requested_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("已选择 CUDA，但当前 Python/PyTorch 未检测到可用 NVIDIA GPU。")
    device_name = "cuda" if requested_device == "auto" and torch.cuda.is_available() else requested_device
    if device_name == "auto":
        device_name = "cpu"
    device = torch.device(device_name)

    emit({"type": "status", "taskId": task_id, "message": "正在从本地磁盘加载模型…"})
    config = _config_from_json(config_path)
    cpu = torch.device("cpu")
    model = _build_model(cpu, config)
    state = _remap_single_codebook_keys(load_file(model_path, device="cpu"))
    model.load_state_dict(state)
    del state
    model.eval()

    if device.type == "cuda":
        emit({"type": "status", "taskId": task_id, "message": "正在将模型迁移到 CUDA（FP16）…"})
        model.half()
        model.condition_provider.float()
        model.to(device)
        model.condition_provider.device = device
        for conditioner in model.condition_provider.conditioners.values():
            if hasattr(conditioner, "device"):
                conditioner.device = device
    else:
        model.to(device)

    tokenizer = MT3Tokenizer(instrument_vocabulary="MT3_FULL_PLUS", max_shift_steps=1001)
    return TranscriptionModel(model=model, tokenizer=tokenizer, device=device), str(device)


def collect_notes(model, audio_path: Path, task_id: str, audio_duration: float,
                  instruments: list[str] | None = None,
                  cfg_coef: float = 1.0, beam_size: int = 1,
                  event_sink: list | None = None) -> list[Note]:
    from muscriptor.events import NoteEndEvent, NoteStartEvent, ProgressEvent

    starts: dict[int, Any] = {}
    notes: list[Note] = []
    for event in model.transcribe(audio_path, batch_size=1, prelude_forcing=True, instruments=instruments,
                                  cfg_coef=cfg_coef, beam_size=beam_size):
        if event_sink is not None:
            event_sink.append(event)
        if isinstance(event, ProgressEvent):
            emit(
                {
                    "type": "progress",
                    "taskId": task_id,
                    "completed": event.completed,
                    "total": event.total,
                }
            )
            continue
        if isinstance(event, NoteStartEvent):
            starts[event.index] = event
            continue
        if isinstance(event, NoteEndEvent):
            start = starts.pop(event.start_event_index, event.start_event)
            program, is_drum = representative_program(start.instrument)
            onset = max(0.0, float(start.start_time))
            if onset >= audio_duration:
                continue
            offset = min(audio_duration, max(float(event.end_time), onset + 0.01))
            notes.append(
                Note(
                    onset=onset,
                    offset=offset,
                    pitch=int(start.pitch),
                    instrument=str(start.instrument),
                    program=program,
                    is_drum=is_drum,
                )
            )
    return notes


def write_midi(notes: list[Note], destination: Path) -> None:
    import mido

    ticks_per_beat = 480
    tempo = 500_000
    midi = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    meta = mido.MidiTrack()
    midi.tracks.append(meta)
    meta.append(mido.MetaMessage("track_name", name="MuScriptor transcription", time=0))
    meta.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    grouped: dict[tuple[str, int, bool], list[Note]] = defaultdict(list)
    for note in notes:
        grouped[(note.instrument, note.program, note.is_drum)].append(note)

    melodic_channels = [channel for channel in range(16) if channel != 9]
    melodic_index = 0
    for track_index, ((name, program, is_drum), track_notes) in enumerate(
        sorted(grouped.items(), key=lambda item: (not item[0][2], item[0][1], item[0][0]))
    ):
        track = mido.MidiTrack()
        midi.tracks.append(track)
        port = 0
        if is_drum:
            channel = 9
        else:
            port, channel_index = divmod(melodic_index, len(melodic_channels))
            channel = melodic_channels[channel_index]
            melodic_index += 1
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.MetaMessage("midi_port", port=port, time=0))
        if not is_drum:
            track.append(mido.Message("program_change", channel=channel, program=program, time=0))

        events: list[tuple[int, int, Any]] = []
        for note in track_notes:
            start_tick = round(mido.second2tick(note.onset, ticks_per_beat, tempo))
            end_tick = max(start_tick + 1, round(mido.second2tick(note.offset, ticks_per_beat, tempo)))
            events.append(
                (start_tick, 1, mido.Message("note_on", channel=channel, note=note.pitch, velocity=88, time=0))
            )
            events.append(
                (end_tick, 0, mido.Message("note_off", channel=channel, note=note.pitch, velocity=0, time=0))
            )
        previous_tick = 0
        for tick, _priority, message in sorted(events, key=lambda item: (item[0], item[1], item[2].note)):
            message.time = tick - previous_tick
            previous_tick = tick
            track.append(message)
    destination.parent.mkdir(parents=True, exist_ok=True)
    midi.save(destination)


VOCALS_MODEL_FILENAME = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"


def detect_beat_grid_lenient(wav_path: Path, task_id: str):
    """Detect the beat grid like muscriptor's detect_grid(), except that a
    free-tempo recording (beats don't fit a constant tempo) keeps the fitted
    average tempo rounded to the nearest whole BPM instead of falling back to
    the placeholder tempo.

    Returns a BeatGrid or None (only when no tempo is detectable at all).
    Mirrors muscriptor.utils.beats.detect_grid so we stay on the official
    beat-this pipeline; the only deliberate difference is the relaxed
    tempo-residual gate.
    """
    import numpy as np
    import soundfile as sf
    from muscriptor.utils import beats as beats_mod

    try:
        from beat_this.inference import Audio2Beats

        signal, sample_rate = sf.read(str(wav_path), dtype="float32", always_2d=True)
        mono = signal.mean(axis=1)
        duration_s = len(mono) / sample_rate
        if duration_s < 1.0:
            raise beats_mod.BeatDetectionError(
                f"Audio is {duration_s:.2f}s long, too short to detect a tempo"
            )
        # Returns (beats, downbeats); same "final0" checkpoint the official
        # detect_grid uses.
        beat_times, downbeats = Audio2Beats(checkpoint_path="final0", device="cpu", dbn=False)(
            mono, sample_rate
        )
        beat_times = np.asarray(beat_times, dtype=float)
        downbeats = np.asarray(downbeats, dtype=float)
        if len(beat_times) < beats_mod.MIN_BEATS:
            raise beats_mod.BeatDetectionError(
                f"Only {len(beat_times)} beats detected, need at least {beats_mod.MIN_BEATS}"
            )
        bpm, residual = beats_mod.fit_tempo(beat_times)
        beat_seconds = 60.0 / bpm
        free_tempo = residual > beats_mod.MAX_TEMPO_RESIDUAL * beat_seconds
        if free_tempo:
            # 四舍五入到整数 BPM，替代回退占位 120 BPM
            bpm = float(max(1, int(bpm + 0.5)))
            emit({
                "type": "status",
                "taskId": task_id,
                "message": f"自由速度音频（节拍 RMS 偏差 {residual * 1000:.0f} ms），按平均速度取整 {bpm:.0f} BPM 记谱",
            })
        beats_per_bar = beats_mod.infer_beats_per_bar(beat_times, downbeats)
        first_downbeat = float(downbeats[0]) if len(downbeats) else float(beat_times[0])
        return beats_mod.BeatGrid(
            bpm=bpm,
            beats_per_bar=beats_per_bar,
            first_downbeat=first_downbeat,
            beats=beat_times,
        ), free_tempo
    except beats_mod.BeatDetectionError as exc:
        emit({
            "type": "status",
            "taskId": task_id,
            "message": f"节拍检测失败（{exc}），回退到占位 120 BPM",
        })
        return None, False
    except Exception as exc:  # beat_this load failures etc.
        emit({
            "type": "status",
            "taskId": task_id,
            "message": f"节拍检测不可用（{exc}），回退到占位 120 BPM",
        })
        return None, False


def postprocess_midi(midi_path: Path, beats_per_bar: int | None) -> None:
    """Humanize velocities and add per-bar sustain pedal (CC64) for piano/guitar.

    The model does not predict dynamics, so: drums (channel 9) get a random
    velocity in 80-90, everything else 60-80. For piano (GM 0-7) and guitar
    (GM 24-31) tracks the sustain pedal goes down at every bar start and comes
    back up a 32nd note before the bar ends. Bar length falls back to 4 beats
    when the meter was not detected.
    """
    import random

    import mido

    midi = mido.MidiFile(str(midi_path))
    tpb = midi.ticks_per_beat
    bar_ticks = (beats_per_bar or 4) * tpb
    up_margin = max(1, tpb // 8)
    rng = random.Random()

    for track in midi.tracks:
        events: list[tuple[int, int, Any]] = []  # (abs_tick, order, message)
        abs_tick = 0
        program: int | None = None
        note_channel = 0
        has_notes = False
        for msg in track:
            abs_tick += msg.time
            if msg.is_meta:
                events.append((abs_tick, 0, msg))
                continue
            if msg.type == "program_change" and program is None:
                program = msg.program
            if msg.type == "note_on" and msg.velocity > 0:
                if not has_notes:
                    note_channel = msg.channel
                has_notes = True
                lo, hi = (80, 90) if msg.channel == 9 else (60, 80)
                msg = msg.copy(velocity=rng.randint(lo, hi))
            # order: meta < note_off/cc < note_on, so pedal-down precedes the
            # bar's first note at the same tick
            events.append((abs_tick, 2 if msg.type == "note_on" and msg.velocity > 0 else 1, msg))
        if not has_notes:
            continue
        if program is not None and (0 <= program <= 7 or 24 <= program <= 31):
            last_tick = max(t for t, _, _ in events)
            for bar in range(last_tick // bar_ticks + 1):
                down = bar * bar_ticks
                up = max(down, (bar + 1) * bar_ticks - up_margin)
                events.append((down, 1, mido.Message(
                    "control_change", channel=note_channel, control=64, value=127, time=0)))
                events.append((up, 1, mido.Message(
                    "control_change", channel=note_channel, control=64, value=0, time=0)))
        events.sort(key=lambda event: (event[0], event[1]))
        rebuilt = mido.MidiTrack()
        cursor = 0
        for tick, _, msg in events:
            msg.time = tick - cursor
            cursor = tick
            rebuilt.append(msg)
        track[:] = rebuilt
    midi.save(str(midi_path))


def separate_vocals(task_id: str, model_dir: Path, source_audio: Path, output_dir: Path) -> str | None:
    """Separate vocals from the original-quality source audio with BS-RoFormer.

    Returns the vocals.wav path on success, or None so the caller falls back
    to rendering the Voice track with the GM choir soundfont.
    """
    ckpt = model_dir / VOCALS_MODEL_FILENAME
    if not ckpt.is_file():
        emit({"type": "status", "taskId": task_id,
              "message": "未找到人声分离模型（" + VOCALS_MODEL_FILENAME + "），人声轨将使用合唱音色。"})
        return None
    import torch

    if not torch.cuda.is_available() or torch.cuda.device_count() == 0:
        emit({"type": "status", "taskId": task_id,
              "message": "未检测到 CUDA，跳过人声分离（CPU 分离耗时过长），人声轨将使用合唱音色。"})
        return None
    emit({"type": "status", "taskId": task_id,
          "message": "正在分离人声（BS-RoFormer）…"})
    try:
        import logging

        from audio_separator.separator import Separator

        destination = output_dir / "vocals.wav"
        separator = Separator(
            log_level=logging.WARNING,
            model_file_dir=str(model_dir),
            output_dir=str(output_dir),
            output_format="WAV",
            sample_rate=44100,
        )
        separator.load_model(model_filename=VOCALS_MODEL_FILENAME)
        separator.separate(str(source_audio))
        vocals_matches = sorted(output_dir.glob("*_(Vocals)_*.wav"))
        if not vocals_matches:
            raise RuntimeError("分离完成但未找到人声输出文件。")
        if vocals_matches[0].resolve() != destination.resolve():
            vocals_matches[0].replace(destination)
        # remove instrumental / any other stems, keep vocals only
        for leftover in output_dir.glob("*_(*)_*.wav"):
            if leftover.resolve() != destination.resolve():
                leftover.unlink(missing_ok=True)
        return str(destination.resolve())
    except Exception as exc:
        emit({"type": "status", "taskId": task_id,
              "message": f"人声分离失败，人声轨将使用合唱音色：{exc}"})
        return None


def transcribe(command: dict[str, Any]) -> None:
    task_id = str(command["taskId"])
    started = time.perf_counter()
    audio_path = Path(command["audioPath"])
    model_path = Path(command["modelPath"])
    config_path = Path(command["configPath"])
    output_dir = Path(command["outputDir"])

    if not audio_path.is_file():
        raise FileNotFoundError(f"\u8f93\u5165\u97f3\u9891\u4e0d\u5b58\u5728: {audio_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    staged_input = output_dir / f"source{audio_path.suffix.lower()}"
    if audio_path.resolve() != staged_input.resolve():
        shutil.copyfile(audio_path, staged_input)
    normalized_path = output_dir / "input-16k-mono.wav"
    emit({"type": "status", "taskId": task_id, "message": "正在解码并标准化音频…"})
    conversion = subprocess.run(
        [
            str(command.get("ffmpegPath", "ffmpeg")),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(staged_input),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(normalized_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if conversion.returncode != 0:
        raise RuntimeError(f"音频解码失败：{conversion.stderr.strip()}")

    import soundfile as sf

    audio_duration = float(sf.info(normalized_path).duration)
    model, device = load_model(model_path, config_path, str(command.get("device", "auto")), task_id)
    emit({"type": "status", "taskId": task_id, "message": "正在识别音符与乐器…"})
    selected = command.get("instruments")
    instruments = [str(name) for name in selected] if isinstance(selected, list) and selected else None
    cfg_coef = float(command.get("cfgCoef", 1.0))
    beam_size = max(1, int(command.get("beamSize", 1)))
    detect_tempo = bool(command.get("detectTempo", False))
    quantize = bool(command.get("quantize", False))
    raw_events: list = []
    notes = collect_notes(model, normalized_path, task_id, audio_duration, instruments,
                          cfg_coef=cfg_coef, beam_size=beam_size, event_sink=raw_events)
    emit({"type": "status", "taskId": task_id, "message": "正在生成多轨 MIDI…"})

    midi_path = output_dir / "transcription.mid"
    result_path = output_dir / "result.json"
    beat_grid_info: dict[str, Any] = {"detected": False}
    midi_shift_seconds = 0.0
    if detect_tempo:
        emit({"type": "status", "taskId": task_id, "message": "正在检测节拍网格…"})
        beat_grid, free_tempo = detect_beat_grid_lenient(normalized_path, task_id)
        if beat_grid is None:
            from muscriptor.utils.midi import PLACEHOLDER_GRID

            beat_grid = PLACEHOLDER_GRID
        else:
            from muscriptor.events import NoteStartEvent

            beat_grid = beat_grid.with_onset_delay(
                [ev.start_time for ev in raw_events if isinstance(ev, NoteStartEvent)]
            )
            beat_grid_info = {
                "detected": True,
                "freeTempo": free_tempo,
                "bpm": round(float(beat_grid.bpm), 2),
                "beatsPerBar": int(beat_grid.beats_per_bar) if beat_grid.beats_per_bar else None,
                "onsetDelayMs": round(1000.0 * float(beat_grid.onset_delay or 0.0), 1),
                "beatSubdivision": beat_grid.beat_subdivision,
            }
        # The MIDI writer moves every note by (bar_offset - onset_delay) so bar
        # lines land on real downbeats; the preview must trim the same amount
        # off the rendered stems to stay aligned with the original vocals.
        midi_delay = float(beat_grid.onset_delay or 0.0)
        midi_shift_seconds = float(beat_grid.bar_offset(min_shift=midi_delay)) - midi_delay
        midi_path.write_bytes(
            model.events_to_midi_bytes(iter(raw_events), beat_grid=beat_grid, quantize=quantize)
        )
        post_beats_per_bar = beat_grid.beats_per_bar
    else:
        write_midi(notes, midi_path)
        post_beats_per_bar = None

    optimize_summary = None
    if bool(command.get("midiOptimize", False)):
        emit({"type": "status", "taskId": task_id, "message": "正在优化 MIDI（重复音/碎音/重叠修复）…"})
        try:
            try:
                from midi_optimize import optimize_midi
            except ImportError:
                from backend.midi_optimize import optimize_midi

            report = optimize_midi(midi_path)
            optimize_summary = report["summary"]
            (output_dir / "correction_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            parts = []
            for key, label in (
                ("fragmentsMerged", "合并碎片"),
                ("overlapsFixed", "修复重叠"),
                ("monoConflictsFixed", "单声部修复"),
                ("duplicatesRemoved", "去除重复"),
                ("shortNotesRemoved", "删除极短伪音"),
                ("structureFixed", "结构修复"),
            ):
                if optimize_summary[key]:
                    parts.append(f"{label} {optimize_summary[key]}")
            detail = "、".join(parts) if parts else "未发现问题"
            emit({
                "type": "status",
                "taskId": task_id,
                "message": f"MIDI 优化完成：{detail}（音符 {optimize_summary['notesBefore']} → {optimize_summary['notesAfter']}）",
            })
        except Exception as exc:
            optimize_summary = None
            emit({"type": "status", "taskId": task_id, "message": f"MIDI 优化失败（{exc}），保留原始 MIDI"})

    postprocess_midi(midi_path, post_beats_per_bar)

    # free transcription model GPU memory before loading the separation model
    del model
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    vocals_path = separate_vocals(task_id, model_path.parent, staged_input, output_dir)
    summaries: dict[tuple[str, int, bool], int] = defaultdict(int)
    for note in notes:
        summaries[(note.instrument, note.program, note.is_drum)] += 1
    instruments = [
        {"name": name, "program": program, "isDrum": is_drum, "notes": count}
        for (name, program, is_drum), count in sorted(summaries.items())
    ]
    result = {
        "taskId": task_id,
        "midiPath": str(midi_path.resolve()),
        "resultPath": str(result_path.resolve()),
        "duration": audio_duration,
        "elapsedSeconds": time.perf_counter() - started,
        "device": device,
        "noteCount": len(notes),
        "instruments": instruments,
        "beatGrid": beat_grid_info,
        "midiShiftSeconds": midi_shift_seconds,
        "notes": [asdict(note) for note in notes],
    }
    if vocals_path:
        result["vocalsPath"] = vocals_path
    if optimize_summary is not None:
        result["midiOptimize"] = optimize_summary
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    emit({"type": "complete", "taskId": task_id, "result": {k: v for k, v in result.items() if k != "notes"}})


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        command: dict[str, Any] = {}
        try:
            command = json.loads(line)
            if command.get("type") != "transcribe":
                raise ValueError("Unsupported command")
            transcribe(command)
            return 0
        except KeyboardInterrupt:
            task_id = str(command.get("taskId", "unknown"))
            emit({"type": "cancelled", "taskId": task_id})
            return 130
        except Exception as exc:
            task_id = str(command.get("taskId", "unknown"))
            emit(
                {
                    "type": "error",
                    "taskId": task_id,
                    "message": str(exc),
                    "details": traceback.format_exc(),
                }
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
