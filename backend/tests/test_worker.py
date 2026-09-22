from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import mido

from backend.worker import Note, write_midi


class MidiExportTests(unittest.TestCase):
    def test_writes_type_one_tracks_with_dedicated_drum_channel(self) -> None:
        notes = [
            Note(0.0, 0.5, 60, "acoustic_piano", 0, False),
            Note(0.25, 0.26, 36, "drums", 0, True),
            Note(0.5, 1.0, 64, "acoustic_piano", 0, False),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "test.mid"
            write_midi(notes, output)
            midi = mido.MidiFile(output)

        self.assertEqual(midi.type, 1)
        self.assertEqual(len(midi.tracks), 3)
        messages = [message for track in midi.tracks for message in track]
        self.assertTrue(any(message.type == "note_on" and message.channel == 9 for message in messages))
        self.assertTrue(any(message.type == "program_change" and message.channel != 9 for message in messages))


if __name__ == "__main__":
    unittest.main()
