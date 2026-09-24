"""Group-dispatch tests for the 34-group stem routing in preview.py."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preview import (CHROMATIC_SUBKEYS, GROUP_BY_LABEL, MODEL_GROUPS,
                     RENDER_ORDER, SourceTrack, classify, dispatch)


def make_track(name: str, programs=None, channels=None,
               min_note=None, max_note=None) -> SourceTrack:
    track = SourceTrack()
    track.name = name
    track.programs = list(programs or [])
    track.channels = set(channels or {0})
    track.min_note = min_note
    track.max_note = max_note
    return track


class GroupDispatchTests(unittest.TestCase):
    def test_all_34_groups_match_underscore_and_space_names(self) -> None:
        self.assertEqual(len(MODEL_GROUPS), 35)
        for group in MODEL_GROUPS:
            if group == "chromatic_percussion":
                continue  # sub-split by program, tested separately
            for name in (group, group.replace("_", " ")):
                track = make_track(name)
                self.assertEqual(dispatch(track), group,
                                 f"name {name!r} should dispatch to {group!r}")

    def test_group_by_label_covers_all_groups(self) -> None:
        for group in MODEL_GROUPS:
            self.assertEqual(GROUP_BY_LABEL[group.replace("_", " ")], group)

    def test_drum_channel_wins_over_name(self) -> None:
        track = make_track("weird name", channels={9})
        self.assertEqual(dispatch(track), "drums")

    def test_chromatic_percussion_subsplit_by_program(self) -> None:
        for program, expected in CHROMATIC_SUBKEYS.items():
            track = make_track("chromatic_percussion", programs=[program])
            self.assertEqual(dispatch(track), expected,
                             f"program {program} -> {expected}")
        # unknown / missing program falls back to tubular bells
        self.assertEqual(dispatch(make_track("chromatic percussion", programs=[99])),
                         "tubular_bells")
        self.assertEqual(dispatch(make_track("chromatic percussion")),
                         "tubular_bells")

    def test_unknown_name_falls_back_to_classify(self) -> None:
        track = make_track("My Weird Lead Synth", programs=[81])
        self.assertEqual(dispatch(track),
                         classify(track.name, track.programs, track.channels,
                                  track.min_note, track.max_note))
        self.assertEqual(dispatch(track), "Solo / Counter Melody")

    def test_render_order_covers_groups_subkeys_and_legacy(self) -> None:
        for group in MODEL_GROUPS:
            self.assertIn(group, RENDER_ORDER)
        for key in ("glockenspiel", "tubular_bells", "xylophone", "marimba", "harp"):
            self.assertIn(key, RENDER_ORDER)
        for legacy in ("Piano", "Drums", "FX / Percussion"):
            self.assertIn(legacy, RENDER_ORDER)
        # chromatic sub-stems render right after the chromatic_percussion slot
        idx = RENDER_ORDER.index("chromatic_percussion")
        self.assertEqual(RENDER_ORDER[idx + 1], "glockenspiel")


if __name__ == "__main__":
    unittest.main()
