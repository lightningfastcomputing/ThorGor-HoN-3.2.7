import struct
import unittest
from unittest.mock import Mock, patch

from thorgor.tools.harness_lifecycle import end_match
from thorgor.tools.harness_motion import movement, order_position
from thorgor.tools.harness_clients import post


class ExtensionTests(unittest.TestCase):
    def test_backend_protocol_port_field_is_independent_of_http_listener_port(self):
        with patch("thorgor.tools.harness_clients.HTTPConnection") as factory:
            response = factory.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b"ok"
            self.assertEqual(post(80, f="new_session", port="11235"), b"ok")
            factory.assert_called_once_with("127.0.0.1", 80, timeout=3)
            self.assertIn("port=11235", factory.return_value.request.call_args.args[2])

    def test_actual_order_layout_uses_a_short_entity_index(self):
        packet = order_position(4227, 13000.5, 14000.25)
        self.assertEqual(len(packet), 17)
        self.assertEqual(struct.unpack("<BffIBHB", packet), (2, 13000.5, 14000.25, 0, 0, 4227, 0))
        for index, x in ((0xFFFF, 1), (-1, 1), (1, float("nan"))):
            with self.assertRaises(ValueError):
                order_position(index, x, 1)

    def test_no_movement_claim_without_native_input_selection(self):
        clients = [Mock(), Mock()]
        events = []
        with patch("thorgor.tools.harness_motion.inspect_heroes", return_value=[
                {"selection_count": 0}, {"selection_count": 0}]):
            with self.assertRaisesRegex(RuntimeError, "control selection"):
                movement(123, clients, Mock(), Mock(), lambda name, fn: fn(),
                         lambda name, **data: events.append((name, data)))
        self.assertEqual(events[-1][0], "movement_blocked")
        for client in clients:
            client.game_command.assert_not_called()

    def test_termination_requires_ended_phase_before_native_context_clear(self):
        client, job = Mock(), Mock()
        job.pid = 100
        job.pids.return_value = {100, 101}
        state = {"phase": 7, "phase_duration": 21000}
        with patch("thorgor.tools.harness_lifecycle.inspect_gameplay",
                   return_value={"phase": 6, "native_match_id": 1}), \
                patch("thorgor.tools.harness_lifecycle.wait_state", return_value=state) as wait, \
                patch("thorgor.tools.harness_lifecycle.module_info", return_value=None):
            result = end_match(101, [client], job, lambda name, fn: fn(), Mock())
        self.assertEqual(result["outcome"], "game_module_unloaded")
        client.reliable.assert_called_once_with(b"\xc6EndMatch 1\0")
        predicate = wait.call_args.args[2]
        self.assertFalse(predicate({"phase": 6}))
        self.assertTrue(predicate({"phase": 7}))
