#!/usr/bin/env python3
"""Browser tests use temporary profiles and executables that only record argv."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'bin/taskspaces'
BROWSERS = {'chromium': 'chromium', 'google-chrome-stable': 'google-chrome',
            'brave': 'BraveSoftware/Brave-Browser', 'brave-origin': 'BraveSoftware/Brave-Origin',
            'microsoft-edge-stable': 'microsoft-edge'}
MOCK = r'''#!/usr/bin/python3
import json, os, sys, time
from pathlib import Path
root = Path(os.environ['MOCK_ROOT'])
cmd, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'events.jsonl').open('a') as out:
    out.write(json.dumps([cmd, args]) + '\n')
if cmd == 'omarchy-cmd-default-browser': print('test-browser.desktop')
elif cmd == 'omarchy-menu-select':
    if os.environ.get('MOCK_CANCEL'): sys.exit(1)
    row = args[int(os.environ.get('MOCK_ROW', '1'))]
    print(row.split('\t', 1)[1])
elif cmd in ('uwsm-app', *json.loads(os.environ['MOCK_BROWSERS'])):
    (root / 'launch.json').write_text(json.dumps([cmd, args]))
    time.sleep(float(os.environ.get('MOCK_LAUNCH_SLEEP', '0')))
elif cmd not in ('omarchy-notification-send', 'notify-send'):
    raise RuntimeError('Forbidden desktop command: ' + cmd)
'''


class BrowserTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='taskspaces-browser-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        mock = self.root / 'mock'
        mock.write_text(MOCK)
        mock.chmod(0o755)
        names = ('omarchy-cmd-default-browser', 'omarchy-menu-select', 'uwsm-app',
                 'omarchy-notification-send', 'omarchy-launch-browser',
                 'omarchy-cmd-browser-handoff', 'omarchy-hyprland-focus-app', 'hyprctl',
                 *BROWSERS, 'firefox', 'zen')
        for name in names:
            (self.bin / name).symlink_to(mock)
        (self.bin / 'python3').symlink_to(shutil.which('python3'))
        self.desktop = self.root / '.local/share/applications/test-browser.desktop'
        self.desktop.parent.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.root), PATH=str(self.bin), MOCK_ROOT=str(self.root),
                        XDG_CONFIG_HOME=str(self.root / 'config'), MOCK_BROWSERS=json.dumps(list(BROWSERS)))
        self.env.pop('XDG_RUNTIME_DIR', None)
        self.browser('chromium')

    def browser(self, binary):
        self.desktop.write_text('[Desktop Entry]\nExec=' + binary + ' %U\n')
        self.state = self.root / 'config' / BROWSERS.get(binary, binary) / 'Local State'
        self.state.parent.mkdir(parents=True, exist_ok=True)

    def profiles(self, profiles):
        self.state.write_text(json.dumps({'profile': {'info_cache': profiles}}))

    def run_browser(self, expected=0):
        before = self.state.read_bytes() if self.state.exists() else None
        result = subprocess.run(['/bin/bash', str(SCRIPT), 'browser'], env=self.env,
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(self.state.read_bytes() if self.state.exists() else None, before)
        self.assertFalse((self.root / 'config/hypr').exists())
        for command in ('omarchy-launch-browser', 'omarchy-cmd-browser-handoff',
                        'omarchy-hyprland-focus-app', 'hyprctl'):
            self.assertEqual(self.events(command), [])
        return result

    def events(self, command):
        file = self.root / 'events.jsonl'
        events = [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []
        return [args for cmd, args in events if cmd == command]

    def launch(self):
        file = self.root / 'launch.json'
        deadline = time.monotonic() + 2
        while not file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(file.exists(), 'mock launch did not run')
        for command in ('omarchy-launch-browser', 'omarchy-cmd-browser-handoff',
                        'omarchy-hyprland-focus-app', 'hyprctl'):
            self.assertEqual(self.events(command), [])
        return json.loads(file.read_text())

    def test_zero_missing_malformed_or_omitted_profiles(self):
        for state in (None, 'not json', '{}', '[]', '{"profile": []}',
                      json.dumps({'profile': {'info_cache': {'Default': {'is_omitted': True}}}})):
            with self.subTest(state=state):
                self.state.unlink(missing_ok=True)
                if state is not None:
                    self.state.write_text(state)
                result = self.run_browser(expected=1)
                self.assertIn('No browser profiles found.', result.stderr)
                self.assertFalse((self.root / 'launch.json').exists())
                self.assertEqual(self.events('omarchy-menu-select'), [])

    def test_one_profile_exact_argv_for_every_supported_browser(self):
        for binary in BROWSERS:
            with self.subTest(binary=binary):
                (self.root / 'launch.json').unlink(missing_ok=True)
                self.browser(binary)
                self.profiles({'Profile 2': {'name': 'Work', 'user_name': 'work@example.test'},
                               'Default': {'is_omitted': True}})
                self.run_browser()
                self.assertEqual(self.launch(), ['uwsm-app', ['--', binary, '--profile-directory=Profile 2',
                                                             '--new-window', 'about:blank']])
                self.assertEqual(self.events('omarchy-menu-select'), [])

    def test_several_profiles_names_emails_and_exact_selection(self):
        self.browser('google-chrome-stable')
        self.profiles({'Default': {'name': 'Home'},
                       'Profile 2': {'name': 'Work', 'user_name': 'work@example.test'}})
        self.env['MOCK_ROW'] = '2'
        self.run_browser()
        menu = self.events('omarchy-menu-select')[0]
        self.assertEqual(menu, ['Chrome - new window here', '󰀄\tHome\tLocal profile',
                                '󰀄\tWork\twork@example.test', '--', '--width', '600'])
        self.assertEqual(self.launch()[1][2], '--profile-directory=Profile 2')

    def test_duplicates_control_characters_and_long_names_remain_unique(self):
        self.profiles({'Default': {'name': 'W\nork\t\x1b', 'user_name': 'a\r@example.test'},
                       'Profile 2': {'name': 'Work', 'user_name': 'a@example.test'},
                       'Profile 3': {'name': 'Z' * 100}, 'Profile 4': {'name': 'Z' * 101}})
        self.run_browser()
        rows = self.events('omarchy-menu-select')[0][1:-3]
        self.assertEqual(rows[:2], ['󰀄\tWork\ta@example.test · Default',
                                    '󰀄\tWork\ta@example.test · Profile 2'])
        self.assertEqual(len(set(rows)), 4)
        for row in rows:
            self.assertLessEqual(len(row.split('\t')[1]), 50)
        self.launch()

    def test_cancel_launches_nothing(self):
        self.profiles({'Default': {'name': 'Home'}, 'Profile 2': {'name': 'Work'}})
        self.env['MOCK_CANCEL'] = '1'
        self.run_browser()
        self.assertFalse((self.root / 'launch.json').exists())

    def test_unsupported_browser_notifies_once_and_changes_nothing(self):
        for binary in ('firefox', 'zen', 'other-browser'):
            with self.subTest(binary=binary):
                self.browser(binary)
                result = self.run_browser(expected=1)
                self.assertIn('New browser windows are not supported for ' + binary + ' yet.', result.stderr)
                self.assertFalse((self.root / 'launch.json').exists())
                self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(len(self.events('omarchy-notification-send')), 3)

    def test_plain_launch_fallback_and_state_directory_override(self):
        (self.bin / 'uwsm-app').unlink()
        self.env['TASKSPACES_BROWSER_STATE_DIR'] = str(self.root / 'fixture')
        self.state = self.root / 'fixture/Local State'
        self.state.parent.mkdir()
        self.profiles({'Default': {'name': 'Local'}})
        self.run_browser()
        self.assertEqual(self.launch(), ['chromium', ['--profile-directory=Default', '--new-window', 'about:blank']])

    def test_launch_is_detached(self):
        self.profiles({'Default': {'name': 'Local'}})
        self.env['MOCK_LAUNCH_SLEEP'] = '1'
        start = time.monotonic()
        self.run_browser()
        self.assertLess(time.monotonic() - start, 0.8)
        self.launch()
        # Let the mock finish before deleting its temporary directory.
        time.sleep(1)

    def test_desktop_lookup_precedence_absolute_exec_and_home_config_fallback(self):
        nix = self.root / '.nix-profile/share/applications/test-browser.desktop'
        nix.parent.mkdir(parents=True)
        nix.write_text('[Desktop Entry]\nExec=' + str(self.bin / 'chromium') + ' %U\n')
        self.profiles({'Default': {'name': 'Local'}})
        self.run_browser()
        self.assertEqual(self.launch()[1][1], 'chromium')
        (self.root / 'launch.json').unlink()
        self.desktop.unlink()
        self.env.pop('XDG_CONFIG_HOME')
        self.state = self.root / '.config/chromium/Local State'
        self.state.parent.mkdir(parents=True)
        self.profiles({'Profile 1': {'name': 'Local'}})
        self.run_browser()
        self.assertEqual(self.launch()[1], ['--', str(self.bin / 'chromium'), '--profile-directory=Profile 1',
                                           '--new-window', 'about:blank'])

    def test_missing_supported_browser_reports_installation_problem(self):
        self.profiles({'Default': {'name': 'Local'}})
        (self.bin / 'chromium').unlink()
        result = self.run_browser(expected=1)
        self.assertIn('Cannot find Chromium', result.stderr)
        self.assertFalse((self.root / 'launch.json').exists())

    def test_help_lists_browser_and_browser_rejects_flags(self):
        for args, expected in ((['--help'], 0), (['browser', '--dry-run'], 2)):
            result = subprocess.run(['/bin/bash', str(SCRIPT), *args], env=self.env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, expected)
            self.assertIn('taskspaces browser', result.stdout + result.stderr)
