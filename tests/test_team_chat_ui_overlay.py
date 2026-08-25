import unittest

from thorgor.patches.client.matchmaking_ui import PATCHES


class TeamChatUiOverlayTests(unittest.TestCase):
    @staticmethod
    def replacement(entry: str) -> bytes:
        return next(patch.replacement for patch in PATCHES if patch.entry == entry)

    def test_gameplay_and_spectator_callbacks_preserve_every_watch_argument(self):
        signature = (
            b"local function AllChatMessages(widget, messageType, channel, message, "
            b"entity, noFormatting, isMe)"
        )
        delegate = (
            b"GameChat.AllChatMessages(widget, messageType, channel, message, "
            b"entity, noFormatting, isMe)"
        )
        for entry in ("ui/scripts/game_new.lua", "ui/scripts/specui.lua"):
            with self.subTest(entry=entry):
                replacement = self.replacement(entry)
                self.assertIn(signature, replacement)
                self.assertIn(delegate, replacement)

    def test_lobby_channel_callback_preserves_widget_and_self_flag(self):
        replacement = self.replacement("ui/scripts/communicator.lua")
        self.assertIn(
            b"AllChatMessages(widget, msgType, channelName, text, entity, "
            b"noFormatting, isSelf)",
            replacement,
        )

    def test_every_chat_boundary_normalizes_the_team_marker(self):
        for entry in (
            "ui/scripts/chat.lua",
            "ui/scripts/game_new.lua",
            "ui/scripts/specui.lua",
            "ui/scripts/communicator.lua",
        ):
            with self.subTest(entry=entry):
                replacement = self.replacement(entry)
                self.assertIn(b"[THORGOR_TEAM]", replacement)
                self.assertIn(b"messageType = '5'" if entry != "ui/scripts/communicator.lua" else b"msgType = '5'", replacement)


if __name__ == "__main__":
    unittest.main()
