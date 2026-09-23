"""Pure-rule MIDI repair pass (Phase 1 of the non-quantizing optimizer plan).

Runs on the written transcription MIDI before velocity/pedal post-processing.
Never quantizes: notes are only deleted, merged across tiny gaps, or truncated
to another note's real onset. No note is ever moved onto a beat grid.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DUPLICATE_ONSET_S = 0.015  # same-pitch onsets closer than this are one detection
SHORT_NOTE_S = 0.030  # non-drum notes shorter than this are artifacts
FRAGMENT_GAP_S = 0.060  # same-pitch gap small enough to be one split note

# GM programs 32-39 = bass, 52-55 = choir/voice: monophonic lines.
MONO_PROGRAMS = frozenset(range(32, 40)) | frozenset(range(52, 56))
MONO_NAME_HINTS = ("bass", "voice")


@dataclass
class _Note:
    pitch: int
    channel: int
    start: int  # absolute tick
    end: int  # absolute tick
    velocity: int
    deleted: bool = False


def _tempo_map(midi) -> list[tuple[int, int]]:
    """[(abs_tick, tempo_us_per_beat)] sorted by tick; later tempo at a tick wins."""
    by_tick: dict[int, int] = {0: 500000}
    for track in midi.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                by_tick[tick] = msg.tempo
    return sorted(by_tick.items())


def _seconds_converter(segments: list[tuple[int, int]], ticks_per_beat: int):
    def to_seconds(tick: int) -> float:
        seconds = 0.0
        for index, (seg_tick, tempo) in enumerate(segments):
            if seg_tick >= tick:
                break
            next_tick = segments[index + 1][0] if index + 1 < len(segments) else tick
            end = min(next_tick, tick)
            seconds += (end - seg_tick) * (tempo / 1_000_000) / ticks_per_beat
        return seconds

    return to_seconds


def _parse_track(track, structure_fixed: list[int]):
    """Split a track into notes + other events (absolute ticks).

    Drops orphan note_offs, closes unclosed notes at the track end, and drops
    byte-identical duplicate meta events at the same tick.
    """
    name = ""
    program: int | None = None
    notes: list[_Note] = []
    others: list[tuple[int, int, Any]] = []  # (tick, order, msg); meta=0, cc/pc=1
    open_notes: dict[tuple[int, int], list[_Note]] = defaultdict(list)
    seen_meta: set[tuple[int, str]] = set()
    tick = 0
    last_tick = 0
    for msg in track:
        tick += msg.time
        last_tick = tick
        if msg.is_meta:
            if msg.type == "end_of_track":
                continue  # re-appended after rebuild
            if msg.type == "track_name" and not name:
                name = msg.name
            key = (tick, repr(msg))
            if key in seen_meta:
                structure_fixed[0] += 1
                continue
            seen_meta.add(key)
            others.append((tick, 0, msg.copy(time=0)))
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            note = _Note(msg.note, msg.channel, tick, tick, msg.velocity)
            open_notes[(msg.channel, msg.note)].append(note)
            notes.append(note)
            continue
        if msg.type == "note_off" or msg.type == "note_on":
            stack = open_notes.get((msg.channel, msg.note))
            if stack:
                note = stack.pop(0)
                note.end = max(tick, note.start + 1)
            else:
                structure_fixed[0] += 1  # orphan note_off
            continue
        if msg.type == "program_change" and program is None:
            program = msg.program
        others.append((tick, 1, msg.copy(time=0)))
    for stack in open_notes.values():
        for note in stack:
            note.end = max(last_tick, note.start + 1)
            structure_fixed[0] += 1  # unclosed note
    return name, program, notes, others


def _pitch_groups(notes: list[_Note]):
    groups: dict[tuple[int, int], list[_Note]] = defaultdict(list)
    for note in notes:
        if not note.deleted:
            groups[(note.channel, note.pitch)].append(note)
    for group in groups.values():
        group.sort(key=lambda note: (note.start, note.end))
    return groups.values()


def _optimize_track(name, program, notes, to_seconds, entries, summary) -> None:
    is_drum_track = all(note.channel == 9 for note in notes)
    if program is not None:
        is_mono = program in MONO_PROGRAMS
    else:
        is_mono = any(hint in name.lower() for hint in MONO_NAME_HINTS)

    def report(action: str, note: _Note, detail: dict[str, Any]) -> None:
        entries.append(
            {
                "track": name,
                "action": action,
                "time": round(to_seconds(note.start), 3),
                "pitch": note.pitch,
                **detail,
            }
        )

    # Rule 2: duplicate notes (every track, drums included).
    for group in _pitch_groups(notes):
        keep: _Note | None = None
        for note in group:
            if (
                keep is not None
                and to_seconds(note.start) - to_seconds(keep.start) <= DUPLICATE_ONSET_S
                and note.start < keep.end
            ):
                note.deleted = True
                summary["duplicatesRemoved"] += 1
                report("duplicate_remove", note, {"keptStart": round(to_seconds(keep.start), 3)})
            else:
                keep = note

    # Rule 3: artifact-short notes (never drums).
    if not is_drum_track:
        for note in notes:
            if note.deleted or note.channel == 9:
                continue
            if to_seconds(note.end) - to_seconds(note.start) < SHORT_NOTE_S:
                note.deleted = True
                summary["shortNotesRemoved"] += 1
                report("short_note_remove", note, {"durationMs": round(1000 * (to_seconds(note.end) - to_seconds(note.start)), 1)})

    # Rules 4+5: same-pitch fragments and overlaps (never drums).
    if not is_drum_track:
        for group in _pitch_groups([note for note in notes if note.channel != 9]):
            index = 0
            while index < len(group) - 1:
                cur, nxt = group[index], group[index + 1]
                gap_s = to_seconds(nxt.start) - to_seconds(cur.end)
                if gap_s < 0:  # overlap
                    truncated_s = to_seconds(nxt.start) - to_seconds(cur.start)
                    if truncated_s < SHORT_NOTE_S:
                        cur.end = max(cur.end, nxt.end)
                        nxt.deleted = True
                        group.pop(index + 1)
                        report("overlap_merge", cur, {"mergedWithStart": round(to_seconds(nxt.start), 3)})
                    else:
                        cur.end = nxt.start
                        report("overlap_truncate", cur, {"newEnd": round(to_seconds(cur.end), 3)})
                        index += 1
                    summary["overlapsFixed"] += 1
                elif gap_s <= FRAGMENT_GAP_S:  # fragment
                    cur.end = max(cur.end, nxt.end)
                    nxt.deleted = True
                    group.pop(index + 1)
                    summary["fragmentsMerged"] += 1
                    report("merge", cur, {"mergedWithStart": round(to_seconds(nxt.start), 3)})
                else:
                    index += 1

    # Rule 6: monophonic lines (voice/bass) - different pitches must not overlap.
    if is_mono and not is_drum_track:
        line = sorted((note for note in notes if not note.deleted), key=lambda note: (note.start, note.pitch))
        prev: _Note | None = None
        for note in line:
            if prev is not None and note.start < prev.end:
                prev.end = note.start
                summary["monoConflictsFixed"] += 1
                if to_seconds(prev.end) - to_seconds(prev.start) < SHORT_NOTE_S:
                    prev.deleted = True
                    report("mono_delete", prev, {"conflictPitch": note.pitch})
                else:
                    report("mono_truncate", prev, {"conflictPitch": note.pitch, "newEnd": round(to_seconds(prev.end), 3)})
            prev = note


def _rebuild_track(track, others, notes) -> None:
    import mido

    events = list(others)
    for note in notes:
        if note.deleted:
            continue
        events.append((note.start, 2, mido.Message("note_on", channel=note.channel, note=note.pitch, velocity=note.velocity, time=0)))
        events.append((note.end, 1, mido.Message("note_off", channel=note.channel, note=note.pitch, velocity=0, time=0)))
    events.sort(key=lambda event: (event[0], event[1]))
    rebuilt = mido.MidiTrack()
    cursor = 0
    for tick, _, msg in events:
        msg.time = tick - cursor
        cursor = tick
        rebuilt.append(msg)
    rebuilt.append(mido.MetaMessage("end_of_track", time=0))
    track[:] = rebuilt


def optimize_midi(midi_path) -> dict[str, Any]:
    """Repair a MIDI file in place. Returns {"summary": ..., "entries": [...]}."""
    import mido

    midi_path = Path(midi_path)
    midi = mido.MidiFile(str(midi_path))
    to_seconds = _seconds_converter(_tempo_map(midi), midi.ticks_per_beat)
    summary = {
        "notesBefore": 0,
        "notesAfter": 0,
        "structureFixed": 0,
        "duplicatesRemoved": 0,
        "shortNotesRemoved": 0,
        "fragmentsMerged": 0,
        "overlapsFixed": 0,
        "monoConflictsFixed": 0,
    }
    entries: list[dict[str, Any]] = []
    for index, track in enumerate(midi.tracks):
        structure_fixed = [0]
        name, program, notes, others = _parse_track(track, structure_fixed)
        summary["structureFixed"] += structure_fixed[0]
        if not notes:
            if structure_fixed[0]:
                _rebuild_track(track, others, notes)
            continue
        summary["notesBefore"] += len(notes)
        _optimize_track(name or f"track_{index}", program, notes, to_seconds, entries, summary)
        summary["notesAfter"] += sum(1 for note in notes if not note.deleted)
        _rebuild_track(track, others, notes)
    midi.save(str(midi_path))
    return {"summary": summary, "entries": entries}
