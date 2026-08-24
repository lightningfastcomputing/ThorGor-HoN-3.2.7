import tempfile
import unittest
from pathlib import Path

from thorgor.master.accounts import AccountStore
from thorgor.matchmaking.endpoint import DedicatedServerAllocator, MatchmakingEndpoint


class MatchmakingEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.temp.name) / "accounts.db")
        self.state = {"lifecycle": "idle", "match_id": 0}
        self.accounts = []
        for name in ("alpha", "bravo"):
            account = self.store.add_or_update(name, "secret", name.title())
            self.accounts.append(self.store.register_game_authorization(account.account_id))
        allocator = DedicatedServerAllocator(
            self.store, lambda: dict(self.state), self.update_state, lambda: True,
            server_id=7, host="192.168.1.154", port=11236,
        )
        self.endpoint = MatchmakingEndpoint(self.store, allocator)

    def tearDown(self):
        self.temp.cleanup()

    def update_state(self, **updates):
        self.state.update(updates)
        return dict(self.state)

    def params(self, index):
        return {"cookie": [self.accounts[index].cookie], "mode": ["allpick"]}

    def test_two_authenticated_players_allocate_and_both_can_poll(self):
        first = self.endpoint.join(self.params(0))
        second = self.endpoint.join(self.params(1))
        polled = self.endpoint.poll(self.params(0))
        self.assertEqual(first["status"], "queued")
        self.assertEqual(second["status"], "assigned")
        self.assertEqual(polled["assignment"]["match_id"], second["assignment"]["match_id"])
        self.assertEqual(second["assignment"]["host"], "192.168.1.154")
        self.assertEqual(self.state["lifecycle"], "allocated")

    def test_invalid_cookie_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid player cookie"):
            self.endpoint.join({"cookie": ["wrong"]})

    def test_unavailable_server_restores_the_queue(self):
        unavailable = MatchmakingEndpoint(
            self.store,
            DedicatedServerAllocator(self.store, lambda: dict(self.state), self.update_state,
                                     lambda: False, server_id=7, host="127.0.0.1", port=11236),
        )
        unavailable.join(self.params(0))
        result = unavailable.join(self.params(1))
        self.assertEqual(result["status"], "queued")
        self.assertEqual(len(unavailable.queue.snapshot()), 2)


if __name__ == "__main__":
    unittest.main()
