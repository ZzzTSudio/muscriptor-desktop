"""Render a MuScriptor MIDI preview with the ZzzTStudio AutoArrange studio bank.

Protocol: one JSON command per line on stdin (UTF-8):
{"type": "preview", "taskId": str, "midiPath": str, "outputPath": str,
 "bankRoot": str, "sfizzPath": str, "sampleRate": int}

Emits JSON lines on stdout:
{"type": "status", ...} {"type": "complete", ...} {"type": "error", ...}

Instrument mapping mirrors AutoArrange's classify-instrument rules, and the
SFZ patch / gain table comes from studio-bank/manifest.json so both apps use
exactly the same timbres.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any


def _configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


_configure_stdio()


def emit(event: dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False), flush=True)


CATEGORIES = [
    "Voice",
    "Piano",
    "Acoustic Guitar",
    "Electric Guitar",
    "Distorted Guitar",
    "Bass",
    "Drums",
    "Strings",
    "Pad",
    "Organ",
    "Pluck / Harp",
    "Mallets",
    "Bells",
    "Timpani",
    "Brass",
    "Woodwinds",
    "Clarinet",
    "Saxophone",
    "Solo / Counter Melody",
    "FX / Percussion",
]

CATEGORY_LABELS_ZH = {
    "Voice": "\u4eba\u58f0(GM Choir Aahs)",
    "Piano": "\u94a2\u7434(Salamander Grand)",
    "Acoustic Guitar": "\u6728\u5409\u4ed6(\u897f\u73ed\u7259\u53e4\u5178)",
    "Electric Guitar": "\u7535\u5409\u4ed6(FSBS \u5e72\u51c0\u6865\u4f4d)",
    "Bass": "\u8d1d\u65af(Pastabass)",
    "Drums": "\u9f13\u7ec4(Naked Drums)",
    "Strings": "\u5f26\u4e50(VPO)",
    "Pad": "\u94fa\u5e95(NewAge)",
    "Organ": "\u7ba1\u98ce\u7434(\u6559\u5802)",
    "Pluck / Harp": "\u7ad6\u7434/\u62e8\u5f26(VPO)",
    "Solo / Counter Melody": "\u4e3b\u594f/\u526f\u65cb\u5f8b(\u957f\u7b1b VPO)",
    "Distorted Guitar": "失真电吉他(FSBS dist1)",
    "Saxophone": "萨克斯(Tenor)",
    "Clarinet": "单簧管",
    "Brass": "铜管(VSCO 小号)",
    "Woodwinds": "木管(VSCO 双簧管)",
    "Timpani": "定音鼓(FreePats)",
    "Mallets": "木琴/马林巴(FreePats)",
    "Bells": "管钟/钢片琴(FreePats)",
    "FX / Percussion": "\u6253\u51fb/\u97f3\u6548(Naked Drums)",
}

NAMED_RULES: list[tuple[str, list[str]]] = [
    ("Piano", ["piano", "keys"]),
    ("Acoustic Guitar", ["acoustic guitar", "a guitar", "nylon", "steel guitar"]),
    ("Distorted Guitar", ["distorted", "distortion", "overdrive"]),
    ("Electric Guitar", ["electric guitar", "e guitar"]),
    ("Drums", ["drum"]),
    ("Voice", ["voice", "vocal", "choir"]),
    ("Strings", ["string", "violin", "viola", "cello"]),
    ("Pad", ["pad", "atmosphere"]),
    ("Organ", ["organ"]),
    ("Mallets", ["xylophone", "marimba", "vibraphone", "mallet"]),
    ("Bells", ["tubular bell", "bell", "glockenspiel", "celesta", "music box"]),
    ("Timpani", ["timpani"]),
    ("Pluck / Harp", ["harp", "pluck"]),
    ("Saxophone", ["sax"]),
    ("Clarinet", ["clarinet"]),
    ("Brass", ["trumpet", "trombone", "tuba", "french horn", "brass"]),
    ("Woodwinds", ["oboe", "english horn", "bassoon"]),
    ("Bass", ["bass"]),
    ("Solo / Counter Melody", ["solo", "flute", "lead", "whistle"]),
    ("FX / Percussion", ["fx", "effect", "percussion", "impact", "riser", "hit"]),
]


def classify(name: str, programs: list[int], channels: set[int],
             min_note: int | None, max_note: int | None) -> str:
    """Port of AutoArrange classifyInstrument()."""
    if 9 in channels:
        return "Drums"
    label = name.lower().replace("_", " ").replace("-", " ")
    # "chromatic percussion" 太笼统（GM 8-15 全组），交给 program 细分判断
    if label != "chromatic percussion":
        for category, words in NAMED_RULES:
            if any(word in label for word in words):
                return category
    if programs:
        program = programs[0]
        if program <= 7:
            return "Piano"
        if program <= 10:
            return "Bells"
        if program <= 13:
            return "Mallets"
        if program == 14:
            return "Bells"
        if program <= 15:
            return "Pluck / Harp"
        if program <= 23:
            return "Organ"
        if program <= 25:
            return "Acoustic Guitar"
        if program <= 28:
            return "Electric Guitar"
        if program <= 31:
            return "Distorted Guitar"
        if program <= 39:
            return "Bass"
        if program == 46:
            return "Pluck / Harp"
        if program == 47:
            return "Timpani"
        if program in (52, 53, 54):
            return "Voice"
        if program <= 55:
            return "Strings"
        if program <= 63:
            return "Brass"
        if program <= 67:
            return "Saxophone"
        if program <= 70:
            return "Woodwinds"
        if program == 71:
            return "Clarinet"
        if program <= 87:
            return "Solo / Counter Melody"
        if program <= 95:
            return "Pad"
        return "FX / Percussion"
    if max_note is not None and max_note < 55:
        return "Bass"
    return "FX / Percussion"


class SourceTrack:
    def __init__(self) -> None:
        self.name = ""
        self.programs: list[int] = []
        self.channels: set[int] = set()
        self.min_note: int | None = None
        self.max_note: int | None = None
        # absolute-tick note events: (abs_tick, kind, pitch, velocity)
        self.events: list[tuple[int, str, int, int]] = []
        # absolute-tick sustain pedal (CC64) events: (abs_tick, value)
        self.sustain: list[tuple[int, int]] = []


def parse_source_tracks(midi_path: Path) -> tuple[int, int, list[SourceTrack]]:
    import mido

    midi = mido.MidiFile(str(midi_path))
    tempo = 500_000
    tracks: list[SourceTrack] = []
    for raw_track in midi.tracks:
        abs_tick = 0
        current = SourceTrack()
        for message in raw_track:
            abs_tick += message.time
            if message.type == "set_tempo":
                tempo = message.tempo
            elif message.type == "track_name" and not current.name:
                current.name = str(message.name)
            elif message.type == "program_change":
                if message.program not in current.programs:
                    current.programs.append(message.program)
            elif message.type == "note_on" and message.velocity > 0:
                current.channels.add(message.channel)
                current.events.append((abs_tick, "on", message.note, message.velocity))
                current.min_note = message.note if current.min_note is None else min(current.min_note, message.note)
                current.max_note = message.note if current.max_note is None else max(current.max_note, message.note)
            elif message.type == "control_change" and message.control == 64:
                current.sustain.append((abs_tick, message.value))
            elif message.type in ("note_off",) or (message.type == "note_on" and message.velocity == 0):
                if message.channel in current.channels or current.events:
                    current.events.append((abs_tick, "off", message.note, 0))
        if any(kind == "on" for _, kind, _, _ in current.events):
            tracks.append(current)
    return midi.ticks_per_beat, tempo, tracks


def write_category_midi(tracks: list[SourceTrack], ticks_per_beat: int,
                        tempo: int, destination: Path,
                        program: int | None = None,
                        include_sustain: bool = False,
                        beat_grid: dict | None = None,
                        sustain_offset_beats: float = 0.125) -> None:
    import mido

    midi = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    meta.append(mido.MetaMessage("end_of_track", time=0))
    midi.tracks.append(meta)

    merged: list[tuple[int, int, Any]] = []
    
    # Generate sustain pedal events for piano/guitar if beat grid is available
    if include_sustain and beat_grid and beat_grid.get("beatsPerBar"):
        beats_per_bar = beat_grid["beatsPerBar"]
        ticks_per_bar = ticks_per_beat * beats_per_bar
        sustain_off_offset = int(ticks_per_beat * sustain_offset_beats)
        
        # Find the last note tick to determine number of bars
        last_tick = 0
        for source in tracks:
            for abs_tick, kind, _, _ in source.events:
                if kind == "on":
                    last_tick = max(last_tick, abs_tick)
        
        if last_tick > 0:
            num_bars = last_tick // ticks_per_bar + 1
            for i in range(num_bars):
                bar_start = i * ticks_per_bar
                bar_end = (i + 1) * ticks_per_bar - sustain_off_offset
                # Sustain on at bar start (priority 1 = before note_on)
                merged.append((bar_start, 1, mido.Message("control_change", channel=0, control=64, value=127, time=0)))
                # Sustain off at bar end (priority 1 = before note_on)
                merged.append((bar_end, 1, mido.Message("control_change", channel=0, control=64, value=0, time=0)))
    
    for source in tracks:
        if include_sustain:
            # Pass through original sustain events only if no beat grid
            if not (beat_grid and beat_grid.get("beatsPerBar")):
                for abs_tick, value in source.sustain:
                    # pedal changes sort before note ons at the same tick
                    merged.append((abs_tick, 1, mido.Message("control_change", channel=0, control=64, value=value, time=0)))
        for abs_tick, kind, pitch, velocity in source.events:
            # offs sort before ons at the same tick
            order = 0 if kind == "off" else 2
            if kind == "off":
                merged.append((abs_tick, order, mido.Message("note_off", channel=0, note=pitch, velocity=0, time=0)))
            else:
                merged.append((abs_tick, order, mido.Message("note_on", channel=0, note=pitch, velocity=velocity, time=0)))
    merged.sort(key=lambda item: (item[0], item[1]))

    track = mido.MidiTrack()
    if program is not None:
        track.append(mido.Message("program_change", channel=0, program=program, time=0))
    cursor = 0
    for abs_tick, _, message in merged:
        message.time = abs_tick - cursor
        cursor = abs_tick
        track.append(message)
    # keep the render alive ~8 beats past the last note for release tails
    track.append(mido.MetaMessage("end_of_track", time=ticks_per_beat * 8))
    midi.tracks.append(track)
    midi.save(str(destination))


def stem_loudness_db(data, sample_rate: int) -> float:
    """Gated block loudness (BS.1770 gating, without K-weighting) in dB.

    Good enough for relative stem balancing; returns -inf for silence.
    """
    import numpy as np

    mono = data.mean(axis=1)
    block = max(1, int(0.4 * sample_rate))
    count = len(mono) // block
    if count == 0:
        rms = float(np.sqrt((mono ** 2).mean())) if mono.size else 0.0
        return -0.691 + 20 * np.log10(rms) if rms > 0 else float("-inf")
    blocks = mono[: count * block].reshape(count, block)
    with np.errstate(divide="ignore"):
        block_db = -0.691 + 10 * np.log10((blocks ** 2).mean(axis=1))
    gate = block_db > -70.0
    if not gate.any():
        return float("-inf")
    mean_ms = float((blocks[gate] ** 2).mean())
    relative = -0.691 + 10 * np.log10(mean_ms) - 10.0
    gate &= block_db > relative
    if not gate.any():
        return float("-inf")
    return float(-0.691 + 10 * np.log10((blocks[gate] ** 2).mean()))


def gain_to_target_db(data, sample_rate: int, target_db: float,
                      min_gain: float = 0.05, max_gain: float = 16.0) -> float:
    measured = stem_loudness_db(data, sample_rate)
    if measured == float("-inf"):
        return 1.0
    gain = 10 ** ((target_db - measured) / 20.0)
    return float(min(max(gain, min_gain), max_gain))


def find_vst3_plugin(search_roots: list[str], name: str) -> Path | None:
    """Locate a VST3 plugin by name under any of the configured search roots.

    Accepts both bundle-style installs (<root>/<name>.vst3/Contents/x86_64-win/<name>.vst3)
    and flat single-file plugins (<root>/<name>.vst3).
    """
    import os

    for raw_root in search_roots:
        root = Path(os.path.expandvars(str(raw_root)))
        bundle = root / f"{name}.vst3"
        inner = bundle / "Contents" / "x86_64-win" / f"{name}.vst3"
        if inner.is_file():
            return inner
        if bundle.is_file() or bundle.is_dir():
            return bundle
    return None


def render_vst3_stem(plugin_path: Path, stem_midi: Path, stem_wav: Path,
                     sample_rate: int) -> None:
    """Render one stem MIDI through a VST3 instrument using DawDreamer."""
    import dawdreamer as daw
    import mido
    import soundfile as sf

    # stem files end with an 8-beat EOT tail; add one extra second for release
    duration = mido.MidiFile(str(stem_midi)).length + 1.0
    engine = daw.RenderEngine(sample_rate, 512)
    processor = engine.make_plugin_processor("stem", str(plugin_path))
    if not processor.load_midi(str(stem_midi)):
        raise RuntimeError(f"VST3 插件无法读取 MIDI: {stem_midi}")
    engine.load_graph([(processor, [])])
    engine.render(duration)
    audio = processor.get_audio()
    if audio.size == 0:
        raise RuntimeError("VST3 插件没有输出音频。")
    sf.write(str(stem_wav), audio.T, sample_rate, subtype="FLOAT")


def render_preview(command: dict[str, Any]) -> dict[str, Any]:
    import soundfile as sf

    midi_path = Path(command["midiPath"])
    output_path = Path(command["outputPath"])
    bank_root = Path(command["bankRoot"])
    sfizz = str(command["sfizzPath"])
    sample_rate = int(command.get("sampleRate", 44100))
    # The MIDI writer shifts every note by (bar_offset - onset_delay) to align
    # bar lines; drop that head from rendered stems so they line up with the
    # separated vocals (which stay on the original timeline).
    midi_shift_frames = max(0, round(float(command.get("midiShift", 0.0) or 0.0) * sample_rate))

    manifest = json.loads((bank_root / "manifest.json").read_text(encoding="utf-8"))
    patches: dict[str, dict[str, Any]] = manifest["instruments"]
    vst3_search_paths: list[str] = list(manifest.get("vst3SearchPaths", []))
    vocals_path = Path(str(command["vocalsPath"])) if command.get("vocalsPath") else None
    if vocals_path is not None and not vocals_path.is_file():
        vocals_path = None

    ticks_per_beat, tempo, source_tracks = parse_source_tracks(midi_path)
    if not source_tracks:
        raise ValueError("MIDI \u4e2d\u6ca1\u6709\u53ef\u6e32\u67d3\u7684\u97f3\u7b26\u3002")

    grouped: dict[str, list[SourceTrack]] = {}
    for track in source_tracks:
        category = classify(track.name, track.programs, track.channels, track.min_note, track.max_note)
        grouped.setdefault(category, []).append(track)

    stems: list[tuple[str, Path, bool]] = []  # (category, wav, is_vocals_overlay)
    vocals_overlay_used = False
    # Optional: keep rendered stems in a caller-provided directory for analysis
    keep_dir = command.get("stemsDir")
    if keep_dir:
        Path(str(keep_dir)).mkdir(parents=True, exist_ok=True)
        tmp_ctx: Any = contextlib.nullcontext(str(keep_dir))
    else:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="muscriptor-preview-")
    with tmp_ctx as tmp:
        tmp_dir = Path(tmp)
        categories = [c for c in CATEGORIES if c in grouped]
        total = len(categories)
        for index, category in enumerate(categories, start=1):
            patch = patches[category]
            if category == "Voice" and vocals_path is not None:
                # overlay the separated real vocals instead of rendering choir
                vocal_data, vocal_rate = sf.read(str(vocals_path), dtype="float32", always_2d=True)
                if vocal_rate != sample_rate:
                    import soxr

                    vocal_data = soxr.resample(vocal_data.T, vocal_rate, sample_rate).T.astype("float32")
                if stem_loudness_db(vocal_data, sample_rate) <= -45.0:
                    emit({"type": "status", "taskId": command["taskId"],
                          "message": "分离人声接近静音（可能是纯乐曲），跳过人声叠加。"})
                else:
                    overlay_wav = tmp_dir / f"{index:02d}.wav"
                    sf.write(str(overlay_wav), vocal_data, sample_rate, subtype="FLOAT")
                    stems.append((category, overlay_wav, True))
                    vocals_overlay_used = True
                    emit({"type": "status", "taskId": command["taskId"],
                          "message": "人声使用原曲分离音轨（BS-RoFormer）。"})
                continue
            stem_midi = tmp_dir / f"{index:02d}.mid"
            stem_wav = tmp_dir / f"{index:02d}.wav"
            engine = str(patch.get("engine", "sfizz"))
            program = patch.get("program")
            include_sustain = category in ("Piano", "Acoustic Guitar", "Electric Guitar")
            beat_grid = command.get("beatGrid")
            write_category_midi(grouped[category], ticks_per_beat, tempo, stem_midi,
                                program=int(program) if program is not None else None,
                                include_sustain=include_sustain,
                                beat_grid=beat_grid)
            emit({"type": "status", "taskId": command["taskId"],
                  "message": f"\u6b63\u5728\u6e32\u67d3\u97f3\u8272 {index}/{total}\uff1a{CATEGORY_LABELS_ZH[category]}"})
            vst3_name = str(patch.get("vst3", "")).strip()
            plugin_path = find_vst3_plugin(vst3_search_paths, vst3_name) if vst3_name else None
            rendered = False
            if plugin_path is not None:
                try:
                    render_vst3_stem(plugin_path, stem_midi, stem_wav, sample_rate)
                    rendered = stem_wav.is_file()
                    if rendered:
                        emit({"type": "status", "taskId": command["taskId"],
                              "message": f"{CATEGORY_LABELS_ZH[category]} 已通过 VST3（{vst3_name}）渲染。"})
                except Exception as exc:
                    emit({"type": "status", "taskId": command["taskId"],
                          "message": f"VST3（{vst3_name}）渲染失败，回退到 SFZ：{exc}"})
            if rendered:
                stems.append((category, stem_wav, False))
                continue
            if vst3_name and plugin_path is None:
                emit({"type": "status", "taskId": command["taskId"],
                      "message": f"未在插件目录中找到 VST3（{vst3_name}），改用 SFZ 音色渲染。"})
            if engine == "fluidsynth":
                fluidsynth = command.get("fluidsynthPath")
                soundfont = command.get("gmSoundfontPath")
                if not fluidsynth or not Path(fluidsynth).is_file():
                    raise FileNotFoundError(
                        "\u7f3a\u5c11 FluidSynth\uff0c\u65e0\u6cd5\u6e32\u67d3\u4eba\u58f0\u3002")
                if not soundfont or not Path(soundfont).is_file():
                    raise FileNotFoundError(
                        "\u7f3a\u5c11 GM \u5408\u5531\u97f3\u6e90\uff08WindowsGM.sf2\uff09\uff0c"
                        "\u65e0\u6cd5\u6e32\u67d3\u4eba\u58f0\u3002")
                completed = subprocess.run(
                    [str(fluidsynth), "-ni", "-F", str(stem_wav), "-r", str(sample_rate),
                     "-g", "1.0", str(soundfont), str(stem_midi)],
                    capture_output=True,
                    timeout=600,
                )
            else:
                sfz = bank_root / patch["sfz"]
                if not sfz.is_file():
                    raise FileNotFoundError(f"\u7f3a\u5c11\u97f3\u8272\u6587\u4ef6: {sfz}")
                quality = "1" if category in ("Drums", "FX / Percussion") else "2"
                completed = subprocess.run(
                    [sfizz, "--sfz", str(sfz), "--midi", str(stem_midi), "--wav", str(stem_wav),
                     "--samplerate", str(sample_rate), "--quality", quality,
                     "--polyphony", "256", "--use-eot"],
                    capture_output=True,
                    timeout=600,
                )
            if completed.returncode != 0 or not stem_wav.is_file():
                detail = (completed.stderr or completed.stdout or b"").decode("utf-8", errors="replace")[-2000:]
                raise RuntimeError(f"sfizz_render \u9000\u51fa\u7801 {completed.returncode}: {detail}")
            stems.append((category, stem_wav, False))

        emit({"type": "status", "taskId": command["taskId"], "message": "\u6b63\u5728\u6df7\u97f3\u2026"})
        import numpy as np

        mix = None
        overlay_mix = None  # separated-vocals stems only (for the M-button toggle)
        for category, stem_wav, is_overlay in stems:
            data, rate = sf.read(str(stem_wav), dtype="float32", always_2d=True)
            if not is_overlay and midi_shift_frames:
                data = data[midi_shift_frames:]
            if rate != sample_rate:
                raise RuntimeError(f"\u91c7\u6837\u7387\u4e0d\u5339\u914d: {rate} != {sample_rate}")
            patch = patches[category]
            trim = float(patch.get("gain", 1.0))
            target = patch.get("lufs")
            if target is not None:
                gain = gain_to_target_db(data, sample_rate, float(target)) * trim
            else:
                gain = trim
            if mix is None:
                mix = data * gain
            else:
                if len(data) > len(mix):
                    mix = np.pad(mix, ((0, len(data) - len(mix)), (0, 0)))
                mix[: len(data)] += data * gain
            if is_overlay:
                if overlay_mix is None:
                    overlay_mix = data * gain
                else:
                    if len(data) > len(overlay_mix):
                        overlay_mix = np.pad(overlay_mix, ((0, len(data) - len(overlay_mix)), (0, 0)))
                    overlay_mix[: len(data)] += data * gain
        if mix is None:
            raise ValueError("no stems rendered")
        # overall loudness target: plain gain when peaks allow, otherwise a
        # gentle tanh limiter so transients do not hold the whole mix down.
        # When a vocals overlay is present we stay purely linear and cap the
        # gain instead, so preview_instrumental + preview_vocals reconstruct
        # the full mix exactly (the player layers them for the M toggle).
        mix_target = float(manifest.get("mixTargetLufs", -13.0))
        mix_loud = stem_loudness_db(mix, sample_rate)
        peak = float(abs(mix).max()) if mix.size else 0.0
        if mix_loud != float("-inf") and peak > 0.0:
            gain = 10 ** ((mix_target - mix_loud) / 20.0)
            if vocals_overlay_used:
                gain = min(gain, 0.98 / peak)
                mix = mix * gain
                overlay_mix = overlay_mix * gain if overlay_mix is not None else None
            elif peak * gain <= 0.98:
                mix = mix * gain
            else:
                drive = gain * peak / 0.98
                mix = 0.98 * np.tanh(drive * (mix / peak)) / np.tanh(drive)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), mix, sample_rate, subtype="PCM_16")
        instrumental_path = None
        vocals_mix_path = None
        if vocals_overlay_used and overlay_mix is not None:
            # instrumental = full minus vocals (exact under the linear gain)
            instrumental = mix
            vocals = overlay_mix
            length = len(instrumental)
            if len(vocals) < length:
                vocals = np.pad(vocals, ((0, length - len(vocals)), (0, 0)))
            elif len(vocals) > length:
                vocals = vocals[:length]
            instrumental = instrumental - vocals
            instrumental_path = output_path.with_name(output_path.stem + '_instrumental.wav')
            vocals_mix_path = output_path.with_name(output_path.stem + '_vocals.wav')
            sf.write(str(instrumental_path), instrumental, sample_rate, subtype="PCM_16")
            sf.write(str(vocals_mix_path), vocals, sample_rate, subtype="PCM_16")

    labels = [CATEGORY_LABELS_ZH[c] for c in categories]
    if vocals_overlay_used:
        labels = ["人声(原曲分离)" if c == "Voice" else label
                  for c, label in zip(categories, labels)]
    result = {
        "outputPath": str(output_path.resolve()),
        "sources": labels,
    }
    if instrumental_path is not None and vocals_mix_path is not None:
        result["instrumentalPath"] = str(instrumental_path.resolve())
        result["vocalsMixPath"] = str(vocals_mix_path.resolve())
    return result


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        command: dict[str, Any] = {}
        try:
            command = json.loads(line)
            if command.get("type") != "preview":
                raise ValueError("Unsupported command")
            result = render_preview(command)
            emit({"type": "complete", "taskId": command["taskId"], **result})
            return 0
        except Exception as exc:
            emit({
                "type": "error",
                "taskId": str(command.get("taskId", "unknown")),
                "message": str(exc),
                "details": traceback.format_exc(),
            })
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
