from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import mido

from backend.midi_optimize import optimize_midi

TPB = 480
TEMPO = 500000  # 120 bpm: 1 tick ~= 1.04 ms; 15ms=14.4t 30ms=28.8t 60ms=57.6t


def build_midi(tracks) -> bytes:
    """tracks: list of (name, program|None, channel, [(start, end, pitch), ...])."""
    midi = mido.MidiFile(type=1, ticks_per_beat=TPB)
    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=TEMPO, time=0))
    midi.tracks.append(meta)
    for name, program, channel, notes in tracks:
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        if program is not None:
            track.append(mido.Message("program_change", channel=channel, program=program, time=0))
        events = []
        for start, end, pitch in notes:
            events.append((start, mido.Message("note_on", channel=channel, note=pitch, velocity=80, time=0)))
            events.append((end, mido.Message("note_off", channel=channel, note=pitch, velocity=0, time=0)))
        cursor = 0
        for tick, msg in sorted(events, key=lambda e: e[0]):
            msg.time = tick - cursor
            cursor = tick
            track.append(msg)
        midi.tracks.append(track)
    return midi


def read_notes(midi: mido.MidiFile, track_index: int):
    """Return [(start_tick, end_tick, pitch)] for one track."""
    open_notes = {}
    notes = []
    tick = 0
    for msg in midi.tracks[track_index]:
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            open_notes[(msg.channel, msg.note)] = tick
        elif msg.type in ("note_off", "note_on"):
            start = open_notes.pop((msg.channel, msg.note), None)
            if start is not None:
                notes.append((start, tick, msg.note))
    return sorted(notes)


class MidiOptimizeTests(unittest.TestCase):
    def run_optimizer(self, midi: mido.MidiFile):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "in.mid"
            midi.save(path)
            report = optimize_midi(path)
            return report, mido.MidiFile(path)

    def test_duplicate_notes_removed(self):
        midi = build_midi([("piano", 0, 0, [(0, 480, 60), (10, 490, 60)])])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["duplicatesRemoved"], 1)
        self.assertEqual(read_notes(out, 1), [(0, 480, 60)])

    def test_short_note_removed_but_drum_kept(self):
        midi = build_midi([
            ("piano", 0, 0, [(0, 20, 60), (480, 960, 64)]),
            ("drums", None, 9, [(0, 10, 36)]),
        ])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["shortNotesRemoved"], 1)
        self.assertEqual(read_notes(out, 1), [(480, 960, 64)])
        self.assertEqual(read_notes(out, 2), [(0, 10, 36)])

    def test_fragment_merged_and_wide_gap_kept(self):
        midi = build_midi([("piano", 0, 0, [(0, 480, 60), (485, 965, 60), (0, 480, 62), (680, 1000, 62)])])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["fragmentsMerged"], 1)
        self.assertEqual(read_notes(out, 1), [(0, 480, 62), (0, 965, 60), (680, 1000, 62)])

    def test_same_pitch_overlap_truncated(self):
        midi = build_midi([("piano", 0, 0, [(0, 500, 60), (400, 900, 60)])])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["overlapsFixed"], 1)
        self.assertEqual(read_notes(out, 1), [(0, 400, 60), (400, 900, 60)])

    def test_overlap_too_short_merges_instead(self):
        # truncating the first note to 380->400 (20 ticks ~= 21ms) is too short, so merge
        midi = build_midi([("piano", 0, 0, [(380, 410, 60), (400, 900, 60)])])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["overlapsFixed"], 1)
        self.assertEqual(read_notes(out, 1), [(380, 900, 60)])

    def test_monophonic_voice_conflict_truncated(self):
        midi = build_midi([("voice", 52, 0, [(0, 600, 60), (400, 900, 64)])])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["monoConflictsFixed"], 1)
        self.assertEqual(read_notes(out, 1), [(0, 400, 60), (400, 900, 64)])

    def test_polyphonic_piano_overlap_kept(self):
        midi = build_midi([("piano", 0, 0, [(0, 600, 60), (400, 900, 64)])])
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["monoConflictsFixed"], 0)
        self.assertEqual(read_notes(out, 1), [(0, 600, 60), (400, 900, 64)])

    def test_structure_repairs(self):
        midi = mido.MidiFile(type=1, ticks_per_beat=TPB)
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name="piano", time=0))
        track.append(mido.Message("program_change", channel=0, program=0, time=0))
        track.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=0))  # orphan
        track.append(mido.Message("note_on", channel=0, note=60, velocity=80, time=480))  # never closed
        track.append(mido.MetaMessage("end_of_track", time=240))
        midi.tracks.append(track)
        report, out = self.run_optimizer(midi)
        self.assertEqual(report["summary"]["structureFixed"], 2)
        self.assertEqual(read_notes(out, 0), [(480, 720, 60)])


if __name__ == "__main__":
    unittest.main()
