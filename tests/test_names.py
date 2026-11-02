"""Exercise the pure naming functions with made-up window titles."""
from pathlib import Path
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'bin/taskspaces'


class NameTests(unittest.TestCase):
    def name(self, cls, title, mode='suggest'):
        result = subprocess.run(
            ['bash', '-c', 'source "$1"; name_value "$2" "$3" "$4"',
             '_', str(SCRIPT), mode, cls, title],
            text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def test_launch_audit_title_shapes(self):
        cases = [
            ('ghostty', 'Ready | 12345678-abcd-4321-abcd-123456789abc', 'Terminal task'),
            ('ghostty', 'Working | 87654321-abcd-4321-abcd-123456789abc', 'Terminal task'),
            ('ghostty', '/home/example/Projects/github/my-app', 'my-app'),
            ('ghostty', 'example@machine:~/code', 'code'),
            ('ghostty', 'nvim workspace-planning-notes.md', 'nvim workspace-planning-notes.md'),
            ('chromium', 'Internationalization guide - Chromium', 'Internationalization guide'),
            ('chromium', 'customer-onboarding-checklist - Notion - Chromium', 'customer-onboarding-checklist'),
            ('libreoffice-calc', 'quarterly_report_final.xlsx - LibreOffice Calc', 'quarterly_report_final'),
            ('mpv', 'video_2026-11-01_12-34-56.mp4 - mpv', 'video_2026-11-01_12-34-56.mp4'),
        ]
        for cls, title, expected in cases:
            with self.subTest(cls=cls, title=title):
                self.assertEqual(self.name(cls, title), expected)

    def test_terminal_paths_and_home_fallback(self):
        for cls in ('foot', 'ghostty', 'com.mitchellh.ghostty', 'Alacritty', 'kitty'):
            for title, expected in (
                    ('~/Projects/github/my-app', 'my-app'),
                    ('/home/example/code/my-app/', 'my-app'),
                    ('example@machine:/srv/my-app', 'my-app'),
                    ('example@machine.test:~/code/my-app', 'my-app'),
                    ('~/.config', '.config'),
                    ('~', 'Terminal task'), ('~/', 'Terminal task'),
                    ('/home/example', 'Terminal task'),
                    ('example@machine:~', 'Terminal task')):
                with self.subTest(cls=cls, title=title):
                    self.assertEqual(self.name(cls, title), expected)
            self.assertEqual(self.name(cls, '', mode='label'), 'Terminal')

    def test_status_and_shell_words_try_next_segment(self):
        for word in 'ready working idle done thinking running waiting busy loading bash zsh fish sh'.split():
            for cls, label in (('foot', 'Terminal'), ('code', 'VS Code')):
                with self.subTest(word=word, cls=cls):
                    self.assertEqual(self.name(cls, word.title()), label + ' task')
                    self.assertEqual(self.name(cls, word.upper() + ' | Project notes'), 'Project notes')
        self.assertEqual(self.name('foot', 'Ready | bash | ~/code/my-app'), 'my-app')
        self.assertEqual(self.name('foot', 'Ready | 12345678-abcd-4321-abcd-123456789abc | Working'), 'Terminal task')

    def test_only_id_shaped_tokens_are_removed(self):
        for token in ('12345678-abcd-4321-abcd-123456789abc', 'abcdef0123456789',
                      'Session0123456789Abcd', '1234567890'):
            with self.subTest(token=token):
                self.assertEqual(self.name('foot', 'Ready | ' + token), 'Terminal task')
        self.assertEqual(self.name('code', 'example@example.test: Project notes'), 'Project notes')
        for title in ('Internationalization', 'customer-onboarding-checklist',
                      'quarterly_report_final.xlsx', 'planning_notes_2026_project',
                      'project-planning-2026-notes'):
            with self.subTest(title=title):
                self.assertEqual(self.name('foot', title), title)


if __name__ == '__main__':
    unittest.main()
