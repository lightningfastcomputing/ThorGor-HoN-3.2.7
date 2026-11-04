import unittest
from unittest.mock import patch

from thorgor.tools.harness import SCENARIOS, run


class HarnessTests(unittest.TestCase):
    def test_failed_scenario_reaps_services_and_removes_runtime(self):
        def fail_scenario(master, chat, passwords, check):
            def fail():
                raise ValueError("private failure detail")
            check("injected_failure", fail)

        with patch.dict(SCENARIOS, auth=fail_scenario):
            report = run("auth")

        self.assertEqual(report["status"], "failed")
        events = {event["name"]: event for event in report["events"]}
        self.assertEqual(events["injected_failure"]["status"], "failed")
        self.assertNotIn("private failure detail", str(report))
        for service in ("master", "chat"):
            self.assertEqual(events[f"{service}_started"]["pid"], events[f"{service}_stopped"]["pid"])
        self.assertEqual(report["events"][-1]["name"], "runtime_removed")
