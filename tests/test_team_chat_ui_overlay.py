import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from thorgor.patches.client.matchmaking_ui import PATCHES, ResourceReplacement, patched_entries


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
        self.assertIn(b"thorgorGameChatText", replacement)
        self.assertIn(b"GameChat.thorgorPlayerVisuals[thorgorName]", replacement)
        self.assertNotIn(b"StripClanTag(thorgorName)", replacement)
        self.assertIn(
            b"thorgorNameHex, thorgorWireColor = string.match(text", replacement
        )
        self.assertNotIn(
            b"thorgorNameHex, thorgorWireColor = text and string.match", replacement
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

    def test_authenticated_sender_replaces_the_borrowed_transport_identity(self):
        replacement = self.replacement("ui/scripts/chat.lua")
        self.assertIn(b"THORGOR_TEAM:([0-9A-F]+)", replacement)
        self.assertIn(b"thorgorWireColor", replacement)
        self.assertIn(b"thorgorWireColor and '^' .. thorgorWireColor", replacement)
        self.assertIn(b"tonumber(value, 16)", replacement)
        self.assertIn(b"thorgorColor .. thorgorName .. ': ^*'", replacement)

    def test_team_chat_uses_the_senders_scoreboard_color_and_portrait(self):
        replacements = b"".join(
            patch.replacement for patch in PATCHES if patch.entry == "ui/scripts/chat.lua"
        )
        self.assertIn(b"thorgorPlayerVisuals[visualName]", replacements)
        self.assertIn(b"color = playerColor", replacements)
        self.assertIn(b"icon = heroIcon", replacements)
        self.assertIn(b"entity = 'THORGOR_PLAYER:'", replacements)
        self.assertIn(b"string.sub(entity, 1, 15) == 'THORGOR_PLAYER:'", replacements)
        self.assertIn(b"GameChat.thorgorPlayerVisuals[string.sub(entity, 16)]", replacements)
        self.assertIn(b"THORGOR_ICON:", replacements)
        self.assertIn(b"imagewidget:SetTexture(string.sub(entity, 14))", replacements)

    def test_multiple_replacements_are_applied_to_one_resource_entry(self):
        source = b"alpha beta gamma"
        digest = hashlib.sha256(source).hexdigest().upper()
        patches = (
            ResourceReplacement("chat.lua", digest, b"alpha", b"one", "first"),
            ResourceReplacement("chat.lua", digest, b"gamma", b"three", "second"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "resources.s2z"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("chat.lua", source)
            self.assertEqual(
                patched_entries(archive, patches)["chat.lua"], b"one beta three"
            )


if __name__ == "__main__":
    unittest.main()
