import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from thorgor.game_manager import dedicated_slave, native_match_id


ROOT = Path(__file__).resolve().parents[1]


def load_reference(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "thorgor" / "runtime" / relative
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GameManagerMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge_reference = load_reference(
            "thorgor_manager_bridge_reference", "hon_manager_status_bridge_v42.py"
        )
        cls.native_reference = load_reference(
            "thorgor_native_match_id_reference", "hon_native_matchid_bridge_v47.py"
        )

    def test_manager_control_frame_builders_match_reference(self):
        payloads = (
            dedicated_slave.status_payload(dedicated_slave.STATUS_SLEEPING),
            dedicated_slave.status_payload(dedicated_slave.STATUS_IDLE),
            dedicated_slave.start_game_payload(
                "LAN Match", "map:caldavar mode:normal", -1, -1, "ascii-nul"
            ),
        )
        expected = (
            self.bridge_reference.status_payload(self.bridge_reference.STATUS_SLEEPING),
            self.bridge_reference.status_payload(self.bridge_reference.STATUS_IDLE),
            self.bridge_reference.start_game_payload(
                "LAN Match", "map:caldavar mode:normal", -1, -1, "ascii-nul"
            ),
        )
        self.assertEqual(payloads, expected)

    def test_manager_control_decoders_match_reference(self):
        wire = b'a:1:{s:8:"match_id";i:42;}'
        self.assertEqual(
            dedicated_slave.parse_start_game_match_id(wire),
            self.bridge_reference.parse_start_game_match_id(wire),
        )
        frame = dedicated_slave.start_game_payload(
            "LAN Match", "map:caldavar", -1, -1, "ascii-nul"
        )
        self.assertEqual(
            dedicated_slave.decode_start_game(frame),
            self.bridge_reference.decode_start_game(frame),
        )

    def test_native_match_id_state_selection_matches_reference(self):
        cases = (
            {},
            {"match_id": 0},
            {"match_id": 0xFFFFFFFF},
            {"match_id": 42},
            {"match_id": "42"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            for payload in cases:
                path.write_text(json.dumps(payload), encoding="utf-8")
                self.assertEqual(
                    native_match_id.desired_match_id(path),
                    self.native_reference.desired_match_id(path),
                )

    def test_native_pointer_contract_matches_reference(self):
        self.assertEqual(
            (
                native_match_id.GAME_SINGLETON_PTR_RVA,
                native_match_id.CGAME_GAMEINFO_OFFSET,
                native_match_id.CGAMEINFO_MATCHID_OFFSET,
                native_match_id.VERIFIED_GAME_DLL_SHA256,
            ),
            (
                self.native_reference.GAME_SINGLETON_PTR_RVA,
                self.native_reference.CGAME_GAMEINFO_OFFSET,
                self.native_reference.CGAMEINFO_MATCHID_OFFSET,
                self.native_reference.VERIFIED_GAME_DLL_SHA256,
            ),
        )


if __name__ == "__main__":
    unittest.main()
