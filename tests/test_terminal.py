import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_switch.errors import SwitchError
from codex_switch.service import helper_command, registry_path
from codex_switch.terminal import install_cli, uninstall_cli, BEGIN, LAUNCHER_MARKER


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "user"
        self.home.mkdir()
        self.helper = Path(self.temp.name) / "Applications" / "中文 ' app.app" / "Contents" / "Helpers" / "codex-switch"
        self.helper.parent.mkdir(parents=True)
        self.helper.write_text("fixture", encoding="utf-8")

    def test_install_idempotent_quotes_paths_and_uninstall_preserves_shell_content(self):
        original = '# 用户配置\nexport KEEP_ME="yes"\n'
        (self.home / ".zshrc").write_text(original, encoding="utf-8")
        launcher = Path(install_cli(self.helper, self.home, "/bin/zsh"))
        install_cli(self.helper, self.home, "/bin/zsh")
        self.assertTrue(launcher.read_text("utf-8").startswith(LAUNCHER_MARKER))
        command = shlex.split(launcher.read_text("utf-8").splitlines()[-1])
        self.assertEqual(command, ["exec", str(self.helper.resolve()), "$@"])
        text = (self.home / ".zshrc").read_text("utf-8")
        self.assertEqual(text.count(BEGIN), 1)
        self.assertTrue(text.startswith(original))
        uninstall_cli(self.home)
        self.assertFalse(launcher.exists())
        self.assertEqual((self.home / ".zshrc").read_text("utf-8"), original)

    def test_foreign_command_is_never_overwritten_or_removed(self):
        launcher = self.home / ".local/bin/codex-switch"
        launcher.parent.mkdir(parents=True)
        launcher.write_text("user command", encoding="utf-8")
        with self.assertRaises(SwitchError):
            install_cli(self.helper, self.home, "/bin/zsh")
        uninstall_cli(self.home)
        self.assertEqual(launcher.read_text(), "user command")
        self.assertFalse((self.home / ".zshrc").exists())

    def test_incomplete_marker_refuses_before_installing_anything(self):
        (self.home / ".zshrc").write_text(BEGIN, encoding="utf-8")
        with self.assertRaises(SwitchError):
            install_cli(self.helper, self.home, "/bin/zsh")
        self.assertFalse((self.home / ".local/bin/codex-switch").exists())

    def test_failed_shell_write_rolls_back_launcher_and_earlier_shell_file(self):
        from codex_switch import terminal
        original = "# keep\n"
        (self.home / ".zprofile").write_text(original, encoding="utf-8")
        real_write = terminal._atomic_write

        def write(path, text, mode):
            if path.name == ".zshrc":
                raise OSError("fixture failure")
            real_write(path, text, mode)

        with patch.object(terminal, "_atomic_write", side_effect=write):
            with self.assertRaises(OSError):
                install_cli(self.helper, self.home, "/bin/zsh")
        self.assertFalse((self.home / ".local/bin/codex-switch").exists())
        self.assertEqual((self.home / ".zprofile").read_text(), original)

    def test_bash_and_no_shell_installation(self):
        install_cli(self.helper, self.home, "/bin/bash")
        self.assertIn(BEGIN, (self.home / ".bash_profile").read_text())
        self.assertIn(BEGIN, (self.home / ".bashrc").read_text())
        self.assertFalse((self.home / ".zshrc").exists())
        uninstall_cli(self.home)
        install_cli(self.helper, self.home, "/bin/fish", configure_shell=False)
        self.assertNotIn(BEGIN, (self.home / ".bashrc").read_text())

    def test_macos_bundle_and_helper_resolve_to_same_helper(self):
        contents = self.helper.parent.parent
        gui = contents / "MacOS/Codex Switch"
        with patch.object(sys, "platform", "darwin"), patch.object(sys, "frozen", True, create=True):
            for executable in (gui, self.helper):
                with patch.object(sys, "executable", str(executable)):
                    self.assertEqual(helper_command(), (str(self.helper.resolve()), []))

    def test_application_data_override_is_respected(self):
        with patch.dict(os.environ, {"CODEX_SWITCH_DATA_HOME": str(self.home)}):
            self.assertEqual(registry_path(), self.home / "homes.json")


if __name__ == "__main__":
    unittest.main()
