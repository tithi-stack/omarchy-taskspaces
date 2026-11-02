#!/usr/bin/env python3
"""Setup touches temporary bindings only; every desktop command is mocked."""
import json
import os
from pathlib import Path
import re
import pty
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'bin/taskspaces'
START = '-- >>> taskspaces (added by `taskspaces setup`; undo with `taskspaces setup --remove`) >>>'
END = '-- <<< taskspaces <<<'
ORIGINAL = '-- Personal bindings\no.bind("SUPER + Q", "Personal", "terminal")\n'
MANUAL = '''-- taskspaces: send the focused window to a task, or finish the task
local taskspaces_bin = os.getenv("HOME") .. "/.config/omarchy/plugins/tithi-stack.taskspaces/bin/taskspaces"
o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")
o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskspaces_bin .. " send --silent")
o.bind("SUPER + D", "Finish task", taskspaces_bin .. " finish")
'''
MOCK = r'''#!/usr/bin/python3
import json, os, re, sys
from pathlib import Path
root = Path(os.environ['MOCK_ROOT'])
file = root / 'mock.json'
cfg = json.loads(file.read_text())
cmd, args = Path(sys.argv[0]).name, sys.argv[1:]
with (root / 'events.jsonl').open('a') as out:
    out.write(json.dumps([cmd, args]) + '\n')
def save(): file.write_text(json.dumps(cfg))
def lua_bind(mask, key, description, serial):
    # Synthetic values, same fields and types as `hyprctl binds -j` on a Lua config:
    # the dispatcher is __lua and arg is an id, never the command text.
    return {'locked': False, 'mouse': False, 'release': False, 'repeat': False, 'longPress': False,
            'non_consuming': False, 'auto_consuming': False, 'has_description': bool(description),
            'modmask': mask, 'submap': '', 'submap_universal': 'false', 'key': key, 'keycode': 0,
            'catch_all': False, 'description': description, 'allow_input_capture': False,
            'dispatcher': '__lua', 'arg': str(serial)}
if cmd == 'hyprctl':
    if args == ['binds', '-j']:
        if cfg.get('bad_binds'):
            print(cfg['bad_binds'])
            sys.exit()
        binds = list(cfg.get('binds', []))
        if cfg.get('reloaded') and not cfg.get('missing_loaded'):
            text = Path(os.environ['TASKSPACES_BINDINGS_FILE']).read_text()
            if 'local taskspaces_bin = ' in text and '-- >>> taskspaces' in text:
                helper = json.loads(re.search(r'local taskspaces_bin = (.+)', text)[1])
                pattern = r'o.bind\("([^"]+)", "([^"]+)", taskspaces_bin \.\. " (send(?: --silent)?|finish|browser|go)"\)'
                for serial, (key, description, action) in enumerate(re.findall(pattern, text), 301):
                    if action == 'browser' and cfg.get('missing_browser'): continue
                    if action == 'go' and cfg.get('missing_go'): continue
                    mods = {'SUPER':64, 'CTRL':4, 'ALT':8, 'SHIFT':1}
                    parts = key.split(' + ')
                    mask = sum(mods[m] for m in parts[:-1])
                    if cfg.get('legacy_exec'):
                        # Older and non-Lua configs: the dispatcher is exec and arg is the command.
                        binds.append({'modmask':mask, 'key':parts[-1].lower(),
                                      'dispatcher':'exec', 'arg': helper + ' ' + action})
                    else:
                        binds.append(lua_bind(mask, parts[-1], description, serial))
        if cfg.get('stale_binds') and cfg.get('reloaded'):
            binds.extend(cfg['stale_binds'])
        if cfg.get('wrong_helper') and cfg.get('reloaded'):
            for bind in binds:
                bind['arg'] = '/other/taskspaces send'
                bind['description'] = 'Another program'
        print(json.dumps(binds))
    elif args == ['reload']:
        cfg['reloaded'] = cfg.get('reloaded', 0) + 1
        text = Path(os.environ['TASKSPACES_BINDINGS_FILE']).read_text()
        cfg.setdefault('reload_files', []).append(text)
        save()
        if cfg.get('reload_fail') and cfg['reloaded'] == 1:
            print('reload failed')
            sys.exit(1)
        print('ok')
    elif args == ['configerrors']:
        print(cfg.get('baseline_errors', ''))
        if cfg.get('config_error') and cfg.get('reloaded') == 1:
            print('bindings.lua: new error')
    else: raise RuntimeError(args)
elif cmd == 'omarchy-menu-select':
    choice = cfg.setdefault('choices', []).pop(0) if cfg.get('choices') else 'No'
    if args[0] == 'Back to a task by name' and choice != 'Add a \"go to task\" shortcut':
        cfg.setdefault('choices', []).insert(0, choice)
        choice = 'Not now'
    if cfg.get('edit_on_menu'):
        Path(os.environ['TASKSPACES_BINDINGS_FILE']).write_text('edited while menu open\n')
    if cfg.get('take_on_menu') and args[0] == 'Add Taskspaces shortcuts?':
        cfg.setdefault('binds', []).append(cfg['take_on_menu'])
    save()
    if choice == 'cancel': sys.exit(1)
    rows = [row.split('\t')[1:] for row in args[1:] if '\t' in row]
    aliases = {'Yes':'Yes, add them', 'Remove':'Yes, remove them', 'Show':'Show me the lines first',
               'No':"No, I'll add them myself", 'Pick':'Pick my own key…', 'Skip':'Skip this shortcut'}
    if choice == 'Alternative':
        print('\t'.join(rows[0]))
    else:
        label = 'No, keep my shortcuts' if choice == 'No' and args[0].startswith('Remove') else aliases.get(choice, choice)
        print('\t'.join(next((r for r in rows if r[0] == label), [label])))
elif cmd == 'omarchy-menu-input':
    value = cfg.setdefault('inputs', []).pop(0) if cfg.get('inputs') else ''
    save()
    print(value)
elif cmd == 'omarchy-cmd-default-browser': print('test-browser.desktop')
elif cmd not in ('omarchy-notification-send', 'notify-send'): raise RuntimeError(cmd)
'''


_serial = [100]


def bind(mask, key, description='Open launcher', **fields):
    """A live shortcut in the shape Hyprland reports for a Lua config."""
    _serial[0] += 2
    return dict(locked=False, mouse=False, release=False, repeat=False, longPress=False,
                non_consuming=False, auto_consuming=False, has_description=bool(description),
                modmask=mask, submap='', submap_universal='false', key=key, keycode=0,
                catch_all=False, description=description, allow_input_capture=False,
                dispatcher='__lua', arg=str(_serial[0]), **fields)


def legacy_bind(mask, key, description='Open launcher', arg='launcher'):
    """The shape of an older or non-Lua config: dispatcher exec, arg is the command."""
    return dict(modmask=mask, key=key, description=description, dispatcher='exec', arg=arg)


def setup_namespace():
    """Run only the definitions of the embedded setup program, never its entry point."""
    text = SCRIPT.read_text()
    body = text[text.index('desktop_task() {'):]
    body = body[body.index("<<'PY'\n") + len("<<'PY'\n"):]
    body = body[:body.index('\ntry:\n    if sys.argv[2]')]
    namespace = {'__name__': 'taskspaces_setup'}
    exec(compile(body, 'taskspaces-setup', 'exec'), namespace)
    return namespace


class SetupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='taskspaces-setup-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bindings = self.root / 'config/hypr/bindings.lua'
        self.bindings.parent.mkdir(parents=True)
        self.bindings.write_text(ORIGINAL)
        self.bindings.chmod(0o640)
        self.stock = self.root / 'stock'
        self.stock.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        mock = self.root / 'mock'
        mock.write_text(MOCK)
        mock.chmod(0o755)
        for name in ('hyprctl', 'omarchy-menu-select', 'omarchy-menu-input', 'omarchy-notification-send',
                     'omarchy-cmd-default-browser'):
            (self.bin / name).symlink_to(mock)
        self.desktop = self.root / '.local/share/applications/test-browser.desktop'
        self.desktop.parent.mkdir(parents=True)
        self.desktop.write_text('[Desktop Entry]\nExec=firefox %U\n')
        # No ambient PATH: missing-tool tests cannot fall through to a real compositor.
        for name in ('python3',):
            (self.bin / name).symlink_to(shutil.which(name))
        self.env = dict(os.environ, HOME=str(self.root), PATH=str(self.bin), MOCK_ROOT=str(self.root),
                        XDG_CONFIG_HOME=str(self.root / 'config'), XDG_STATE_HOME=str(self.root / 'state'),
                        TASKSPACES_BINDINGS_FILE=str(self.bindings), TASKSPACES_STOCK_BINDINGS_DIR=str(self.stock))
        self.env.pop('XDG_RUNTIME_DIR', None)
        self.cfg = {'choices': ['Yes']}

    def run_setup(self, *args, expected=0, stdin=None):
        (self.root / 'mock.json').write_text(json.dumps(self.cfg))
        result = subprocess.run(['/bin/bash', str(SCRIPT), 'setup', *args], env=self.env,
                                capture_output=True, text=True, timeout=15, stdin=stdin)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.cfg = json.loads((self.root / 'mock.json').read_text())
        return result

    def events(self, command=None):
        file = self.root / 'events.jsonl'
        items = [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []
        return [args for cmd, args in items if command is None or cmd == command]

    def non_go_menus(self):
        # Existing core/browser assertions ignore the separate optional Go-to question.
        return [menu for menu in self.events('omarchy-menu-select')
                if menu[0] != 'Back to a task by name']

    def backups(self):
        return list((self.root / 'state/taskspaces/backups').glob('bindings.lua.*'))

    def unchanged(self, original=ORIGINAL):
        self.assertEqual(self.bindings.read_text(), original)
        self.assertEqual(self.backups(), [])
        self.assertNotIn(['reload'], self.events('hyprctl'))

    def test_go_shortcut_offer_upgrade_verify_and_remove(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes'], 'legacy_exec': legacy}
                self.run_setup()
                self.assertIn('o.bind("SUPER + ALT + T", "Go to task", taskspaces_bin .. " go")', self.bindings.read_text())
                self.assertEqual(self.cfg['reloaded'], 1)
                self.cfg['choices'] = ['Remove']
                self.run_setup('--remove')
                self.assertEqual(self.bindings.read_text(), ORIGINAL)
        core = self.core_block()
        self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes']}
        self.run_setup()
        expected = core.replace(END, 'o.bind("SUPER + ALT + T", "Go to task", taskspaces_bin .. " go")\n' + END)
        self.assertEqual(self.bindings.read_text(), expected)
        self.assertEqual(self.backups()[-1].read_text(), core)

    def test_go_conflict_fallback_own_key_skip_and_dry_run(self):
        for taken, choice, expected in (([bind(72, 'T')], 'Alternative', 'SUPER + ALT + J'),
                                         ([bind(72, 'T'), bind(72, 'J')], 'Pick', 'SUPER + F8'),
                                         ([bind(72, 'T'), bind(72, 'J')], 'Skip', None)):
            with self.subTest(expected=expected):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': taken, 'choices': ['Add a "go to task" shortcut', choice, 'Yes'],
                            'inputs': ['SUPER + F8']}
                result = self.run_setup('--dry-run')
                if expected:
                    self.assertIn('o.bind("' + expected + '", "Go to task"', result.stdout)
                else:
                    self.assertNotIn(' go")', result.stdout)
                self.unchanged()

    def test_go_missing_loaded_and_stale_removal_roll_back(self):
        self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes'], 'missing_go': True}
        result = self.run_setup(expected=1)
        self.assertIn('restored and reloaded', result.stderr)
        self.assertEqual(self.bindings.read_text(), ORIGINAL)
        self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes']}
        self.run_setup()
        before = self.bindings.read_bytes()
        self.cfg = {'choices': ['Remove'], 'stale_binds': [bind(72, 'T', 'Go to task')]}
        self.run_setup('--remove', expected=1)
        self.assertEqual(self.bindings.read_bytes(), before)

    def test_go_offer_order_and_existing_browser_upgrade(self):
        self.support_browser()
        self.cfg = {'choices': ['Add a "go to task" shortcut', 'Add a "new browser window here" shortcut', 'Yes']}
        self.run_setup()
        self.assertEqual([m[0] for m in self.events('omarchy-menu-select')], [
            'Back to a task by name',
            'Browser windows can jump back to where the browser was first opened',
            'Add Taskspaces shortcuts?'])
        original = self.bindings.read_text()
        self.assertLess(original.index(' go")'), original.index(' browser")'))
        self.cfg = {}
        (self.root / 'events.jsonl').unlink()
        self.run_setup()
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.assertEqual(self.bindings.read_text(), original)
        # An existing browser line does not prevent adding the missing Go-to line.
        before = original.replace('o.bind("SUPER + ALT + T", "Go to task", taskspaces_bin .. " go")\n', '')
        self.bindings.write_text(before)
        self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes']}
        self.run_setup()
        self.assertEqual(self.bindings.read_text().count(' browser")'), 1)
        self.assertEqual(self.bindings.read_text().count(' go")'), 1)
        self.assertIn(before, [backup.read_text() for backup in self.backups()])

    def test_go_key_taken_at_consent_and_wrong_label_or_key_roll_back(self):
        self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes'], 'take_on_menu': bind(72, 'T')}
        self.assertIn('just taken', self.run_setup(expected=1).stderr)
        self.unchanged()
        for stale in (bind(72, 'J', 'Go to task'), bind(72, 'T', 'Another action')):
            self.cfg = {'choices': ['Add a "go to task" shortcut', 'Yes'],
                        'missing_go': True, 'stale_binds': [stale]}
            self.assertIn('did not load every selected', self.run_setup(expected=1).stderr)
            self.assertEqual(self.bindings.read_text(), ORIGINAL)

    def test_go_keys_free_in_installed_stock_bindings(self):
        files = sorted(Path('/usr/share/omarchy/default/hypr/bindings').glob('*.lua'))
        if not files:
            self.skipTest('Omarchy stock bindings are not installed')
        for file in files:
            (self.stock / file.name).write_bytes(file.read_bytes())
        for taken, key in (([], 'SUPER + ALT + T'), ([bind(72, 'T')], 'SUPER + ALT + J')):
            core = self.core_block()
            self.cfg = {'binds': taken, 'choices': ['Add a "go to task" shortcut'] +
                        (['Alternative'] if taken else []) + ['Yes']}
            result = self.run_setup('--dry-run')
            self.assertIn('o.bind("' + key + '", "Go to task"', result.stdout)
            self.unchanged(core)

    def test_free_yes_exact_block_backup_atomic_permissions_and_idempotency(self):
        inode = self.bindings.stat().st_ino
        result = self.run_setup()
        block = '\n'.join([START, 'local taskspaces_bin = ' + json.dumps(str(SCRIPT)),
                           'o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")',
                           'o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskspaces_bin .. " send --silent")',
                           'o.bind("SUPER + D", "Finish task", taskspaces_bin .. " finish")', END, ''])
        self.assertEqual(self.bindings.read_text(), ORIGINAL + block)
        self.assertEqual(self.backups()[0].read_text(), ORIGINAL)
        self.assertEqual(self.bindings.stat().st_mode & 0o777, 0o640)
        self.assertNotEqual(self.bindings.stat().st_ino, inode)
        self.assertEqual(list(self.bindings.parent.glob('.taskspaces-*')), [])
        self.assertEqual(self.cfg['reload_files'], [ORIGINAL + block])
        self.assertIn('Ready: Super+N sends a window to a task, Super+D finishes it.', result.stderr.replace(', Super+Alt+N sends without following', ''))
        before = self.bindings.read_bytes()
        count = len(self.events())
        self.assertIn('Already set up', self.run_setup().stderr)
        self.assertEqual(self.bindings.read_bytes(), before)
        self.assertEqual(len(self.backups()), 1)
        self.assertFalse(any(e[0] == 'reload' for e in self.events('hyprctl')[count:]))

    def test_show_then_yes_displays_exact_lines_and_same_consent(self):
        self.cfg['choices'] = ['Show', 'Yes']
        result = self.run_setup()
        self.assertEqual(result.stdout, self.bindings.read_text()[len(ORIGINAL):])
        menus = self.non_go_menus()
        self.assertEqual(menus[0], menus[1])
        self.assertIn('your bindings file is backed up first', menus[0][1])
        self.assertIn('Super+D finish', menus[0][1])
        for row in menus[0][1:-3]:
            self.assertLessEqual(len(row.split('\t')[1]), 50)

    def test_no_and_cancel(self):
        for choice in ('No', 'cancel', 'unrecognized reply'):
            with self.subTest(choice=choice):
                self.cfg['choices'] = [choice]
                self.run_setup()
                self.unchanged()

    def test_managed_block_already_set_up_without_hyprctl(self):
        self.bindings.write_text(ORIGINAL + START + '\n' + MANUAL + END + '\n')
        (self.bin / 'hyprctl').unlink()
        result = self.run_setup()
        self.assertIn('Already set up', result.stderr)
        self.assertIn('SUPER + N send', result.stderr)
        self.unchanged(ORIGINAL + START + '\n' + MANUAL + END + '\n')

    def test_manual_snippet_already_set_up_and_actual_keys(self):
        text = MANUAL.replace('SUPER + D', 'SUPER + SHIFT + D')
        self.bindings.write_text(text)
        result = self.run_setup()
        self.assertIn('SUPER + SHIFT + D finish', result.stderr)
        self.unchanged(text)
        self.assertEqual(self.events('hyprctl'), [])

    def test_each_default_taken_uses_free_alternative(self):
        for mask, key, expected in ((64, 'n', 'SUPER + SHIFT + T'), (72, 'N', 'SUPER + SHIFT + ALT + T'),
                                    (64, 'd', 'SUPER + SHIFT + D')):
            with self.subTest(mask=mask, key=key):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': [bind(mask, key)], 'choices': ['Alternative', 'Yes']}
                result = self.run_setup()
                self.assertIn('o.bind("' + expected + '"', self.bindings.read_text())
                self.assertIn('already used by "Open launcher"', self.non_go_menus()[-2][0])
                if mask == 64 and key == 'n':
                    self.assertIn('SUPER + SHIFT + ALT + T', self.bindings.read_text())
                    self.assertIn('Super+Shift+T sends', result.stderr)

    def test_send_fallbacks_are_free_in_stock_and_offered_in_order(self):
        folder = Path('/usr/share/omarchy/default/hypr/bindings')
        files = sorted(folder.glob('*.lua'))
        if not files:
            self.skipTest('Omarchy stock bindings are not installed')
        for file in files:
            (self.stock / file.name).write_bytes(file.read_bytes())
        candidates = ('SUPER + SHIFT + T', 'SUPER + SHIFT + H', 'SUPER + SHIFT + J')
        space = setup_namespace()
        self.assertEqual(space['CANDIDATES']['send'], candidates)
        other = {space['parse_key'](key)
                 for action, keys in space['CANDIDATES'].items() if action != 'send'
                 for key in keys}
        taken = [bind(64, 'N')]
        for expected in candidates:
            with self.subTest(expected=expected):
                self.cfg = {'binds': list(taken), 'choices': ['Alternative', 'Yes']}
                result = self.run_setup('--dry-run')
                self.assertIn('o.bind("' + expected + '", "Send window to task"', result.stdout)
                self.assertNotIn(space['parse_key'](expected), other)
                self.unchanged()
                taken.append(bind(65, expected.rsplit(' + ', 1)[1]))
        self.cfg = {'binds': taken, 'choices': ['Skip', 'Yes']}
        result = self.run_setup('--dry-run')
        self.assertNotIn(' send")', result.stdout)
        self.assertFalse(any('Use ' in row for row in self.events('omarchy-menu-select')[-2][1:]))
        self.unchanged()

    def test_stock_defaults_excluded_from_alternatives_and_custom_keys(self):
        (self.stock / 'stock.lua').write_text('o.bind("SUPER + SHIFT + D", "Stock", "stock")\n')
        self.cfg = {'binds': [bind(64, 'D')], 'choices': ['Alternative', 'Yes']}
        self.run_setup()
        self.assertIn('SUPER + CTRL + D', self.bindings.read_text())

    def test_first_free_candidate_order_and_no_alternative(self):
        self.cfg = {'binds': [bind(64, 'D'), bind(65, 'D'), bind(68, 'D')],
                    'choices': ['Alternative', 'Yes']}
        self.run_setup()
        self.assertIn('SUPER + E', self.bindings.read_text())
        self.bindings.write_text(ORIGINAL)
        self.cfg = {'binds': [bind(64, 'D'), bind(65, 'D'), bind(68, 'D'), bind(64, 'E')],
                    'choices': ['Skip', 'Yes']}
        self.run_setup()
        menu = self.non_go_menus()[-2]
        self.assertFalse(any('Use ' in row for row in menu[1:]))
        self.assertNotIn(' finish")', self.bindings.read_text())

    def test_pick_valid_invalid_then_taken_then_valid(self):
        self.cfg = {'binds': [bind(64, 'D'), bind(65, 'E')], 'choices': ['Pick', 'Yes'],
                    'inputs': ['SUPER + D; touch /tmp/no', 'super + shift + e', 'super + ctrl + shift + d']}
        result = self.run_setup()
        self.assertEqual(len(self.events('omarchy-menu-input')), 3)
        self.assertIn('SUPER + CTRL + SHIFT + D', self.bindings.read_text())
        self.assertIn('already used', result.stderr)

    def test_custom_key_rejects_stock_and_selected_keys(self):
        (self.stock / 'stock.lua').write_text('o.bind("SUPER + E", "Stock", "stock")\n')
        self.cfg = {'binds': [bind(64, 'D')], 'choices': ['Pick', 'Yes'],
                    'inputs': ['SUPER + E', 'SUPER + N', 'SUPER + CTRL + D']}
        self.run_setup()
        self.assertEqual(len(self.events('omarchy-menu-input')), 3)
        self.assertIn('SUPER + CTRL + D', self.bindings.read_text())

    def test_three_invalid_attempts_skip_with_cli_message(self):
        self.cfg = {'binds': [bind(64, 'D')], 'choices': ['Pick', 'Yes'],
                    'inputs': ['D', 'SUPER + SUPER + D', 'HYPER + D', 'SUPER + F2']}
        result = self.run_setup()
        self.assertEqual(len(self.events('omarchy-menu-input')), 3)
        self.assertNotIn(' finish")', self.bindings.read_text())
        self.assertIn('still works from the command line', result.stderr)

    def test_skip_send_also_skips_silent(self):
        self.cfg = {'binds': [bind(64, 'N')], 'choices': ['Skip', 'Yes']}
        result = self.run_setup()
        self.assertNotIn(' send', self.bindings.read_text())
        self.assertIn('Super+D finishes', result.stderr)
        self.assertNotIn('Super+N sends', result.stderr)

    def test_skip_all_writes_nothing(self):
        self.cfg = {'binds': [bind(64, 'N'), bind(64, 'D')], 'choices': ['Skip', 'Skip']}
        self.run_setup()
        self.unchanged()

    def test_silent_custom_conflict_and_skip(self):
        self.cfg = {'binds': [bind(72, 'N')], 'choices': ['Pick', 'Yes'], 'inputs':['SUPER + CTRL + ALT + N']}
        self.run_setup()
        self.assertIn('SUPER + CTRL + ALT + N', self.bindings.read_text())
        self.bindings.write_text(ORIGINAL)
        self.cfg = {'binds': [bind(72, 'N')], 'choices': ['Skip', 'Yes']}
        self.run_setup()
        self.assertNotIn('--silent', self.bindings.read_text())

    def test_conflict_title_falls_back_and_sanitizes(self):
        self.cfg = {'binds': [bind(64, 'D', description='\n"Bad\x1b\tname"')], 'choices': ['Skip', 'No']}
        self.run_setup()
        self.assertEqual(self.non_go_menus()[0][0], 'Super+D is already used by "Bad name"')
        # A Lua shortcut has no command text to show: arg is only an id.
        self.cfg = {'binds': [bind(64, 'D', description='')], 'choices': ['Skip', 'No']}
        self.run_setup()
        self.assertEqual(self.non_go_menus()[-2][0],
                         'Super+D is already used by "another shortcut"')
        self.cfg = {'binds': [legacy_bind(64, 'D', description='')], 'choices': ['Skip', 'No']}
        self.run_setup()
        self.assertIn('exec launcher', self.non_go_menus()[-2][0])

    def test_missing_or_unreadable_hyprctl(self):
        for bad in ('not json', '{}', '[{}]', '[{"key":"D","modmask":"64"}]'):
            with self.subTest(bad=bad):
                self.cfg = {'bad_binds': bad}
                self.assertIn('Cannot read live shortcuts', self.run_setup(expected=1).stderr)
                self.unchanged()
        (self.bin / 'hyprctl').unlink()
        self.assertIn('hyprctl is missing', self.run_setup(expected=1).stderr)
        self.unchanged()

    def test_missing_and_read_only_file(self):
        self.bindings.unlink()
        self.assertIn('Bindings file is missing', self.run_setup(expected=1).stderr)
        self.assertFalse(self.bindings.exists())
        self.bindings.write_text(ORIGINAL)
        self.bindings.chmod(0o444)
        self.assertIn('not writable', self.run_setup(expected=1).stderr)
        self.unchanged()

    def test_symlink_target_is_written_and_link_preserved(self):
        target = self.root / 'dotfiles.lua'
        self.bindings.rename(target)
        self.bindings.symlink_to(target)
        self.run_setup()
        self.assertTrue(self.bindings.is_symlink())
        self.assertIn(START, target.read_text())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.backups()[0].read_text(), ORIGINAL)
        self.cfg['choices'] = ['Remove']
        self.run_setup('--remove')
        self.assertTrue(self.bindings.is_symlink())
        self.assertEqual(target.read_text(), ORIGINAL)

    def test_xdg_config_default_path(self):
        self.env.pop('TASKSPACES_BINDINGS_FILE')
        # Mock still needs a path; the default is exercised by a separate mock env key.
        self.env['TASKSPACES_BINDINGS_FILE'] = ''
        self.cfg['choices'] = ['No']
        self.run_setup()
        self.unchanged()

    def test_reload_failure_configerrors_missing_binds_wrong_helper_rollback(self):
        for failure in ('reload_fail', 'config_error', 'missing_loaded', 'wrong_helper'):
            with self.subTest(failure=failure):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {failure: True, 'choices': ['Yes']}
                result = self.run_setup(expected=1)
                self.assertEqual(self.bindings.read_text(), ORIGINAL)
                self.assertIn('restored and reloaded', result.stderr)
                self.assertEqual(self.cfg['reloaded'], 2)
                self.assertEqual(self.backups()[-1].read_text(), ORIGINAL)
                self.assertEqual(list(self.bindings.parent.glob('.taskspaces-*')), [])

    def test_existing_configerrors_are_not_new_errors(self):
        self.cfg['baseline_errors'] = 'an existing unrelated warning'
        self.run_setup()
        self.assertIn(START, self.bindings.read_text())

    def test_remove_block_only_backs_up_and_confirms(self):
        self.run_setup()
        text = self.bindings.read_text() + '-- Keep this tail\n'
        self.bindings.write_text(text)
        self.cfg['choices'] = ['Remove']
        result = self.run_setup('--remove')
        self.assertEqual(self.bindings.read_text(), ORIGINAL + '-- Keep this tail\n')
        self.assertIn(text, [backup.read_text() for backup in self.backups()])
        self.assertIn('shortcuts removed', result.stderr)

    def test_remove_none_and_manual_snippet_never_touched(self):
        self.assertIn('Nothing to remove', self.run_setup('--remove').stderr)
        self.unchanged()
        self.bindings.write_text(MANUAL)
        result = self.run_setup('--remove')
        self.assertIn('hand-added', result.stderr)
        self.assertIn('lines 3, 4, 5', result.stderr)
        self.unchanged(MANUAL)

    def test_remove_requires_yes(self):
        self.run_setup()
        before = self.bindings.read_bytes()
        self.cfg['choices'] = ['No']
        self.run_setup('--remove')
        self.assertEqual(self.bindings.read_bytes(), before)
        self.assertEqual(len(self.backups()), 1)

    def test_remove_verification_failure_rolls_back(self):
        self.run_setup()
        before = self.bindings.read_bytes()
        self.cfg = {'choices':['Remove'], 'config_error': True}
        self.run_setup('--remove', expected=1)
        self.assertEqual(self.bindings.read_bytes(), before)

    def test_dry_run_outputs_exact_block_but_writes_and_reloads_nothing(self):
        before = sorted(str(p) for p in self.root.rglob('*') if p.parent != self.bin)
        result = self.run_setup('--dry-run')
        self.assertTrue(result.stdout.startswith(START + '\n'))
        self.assertTrue(result.stdout.endswith(END + '\n'))
        self.unchanged()
        self.assertFalse((self.root / 'state').exists())
        after = sorted(str(p) for p in self.root.rglob('*') if p.parent != self.bin
                       and p.name not in ('events.jsonl', 'mock.json'))
        self.assertEqual(before, after)

    def test_file_changed_while_menu_open_is_not_overwritten(self):
        self.cfg['edit_on_menu'] = True
        self.assertIn('changed while setup was open', self.run_setup(expected=1).stderr)
        self.assertEqual(self.bindings.read_text(), 'edited while menu open\n')
        self.assertEqual(self.backups(), [])

    def test_key_taken_during_consent_is_not_replaced(self):
        self.cfg['take_on_menu'] = bind(64, 'D')
        self.assertIn('just taken', self.run_setup(expected=1).stderr)
        self.unchanged()

    def test_malformed_markers_stop_without_edits(self):
        for text in (START + '\n', END + '\n', END + '\n' + START + '\n'):
            self.bindings.write_text(text)
            self.assertIn('damaged markers', self.run_setup(expected=1).stderr)
            self.unchanged(text)

    def test_no_menu_and_no_terminal_stops_without_writes(self):
        (self.bin / 'omarchy-menu-select').unlink()
        self.assertIn('menu or a terminal', self.run_setup(expected=1).stderr)
        self.unchanged()

    def test_terminal_fallback_no_then_yes(self):
        (self.bin / 'omarchy-menu-select').unlink()
        for answer in (b'n\n', b'y\n'):
            master, slave = pty.openpty()
            try:
                os.write(master, b'n\n' + answer)
                result = self.run_setup(stdin=slave)
            finally:
                os.close(master)
                os.close(slave)
            self.assertIn('[y/N]', result.stdout)
            if answer == b'n\n':
                self.unchanged()
            else:
                self.assertIn(START, self.bindings.read_text())

    def test_stock_toggle_shortcut_is_reserved(self):
        (self.stock / 'stock.lua').write_text(
            'o.bind_toggle("SUPER + SHIFT + D", "Toggle something", "something")\n')
        self.cfg = {'binds': [bind(64, 'D')], 'choices': ['Alternative', 'Yes']}
        self.run_setup()
        self.assertIn('SUPER + CTRL + D', self.bindings.read_text())

    def test_missing_stock_directory_stops_without_edits(self):
        self.stock.rmdir()
        self.assertIn('Cannot read Omarchy default shortcuts', self.run_setup(expected=1).stderr)
        self.unchanged()

    def test_each_conflicting_default_accepts_custom_after_invalid_and_taken(self):
        for mask, key in ((64, 'N'), (72, 'N'), (64, 'D')):
            with self.subTest(mask=mask, key=key):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': [bind(mask, key)], 'choices': ['Pick', 'Yes'],
                            'inputs': ['SUPER + ?', 'SUPER + ' + ('ALT + ' if mask == 72 else '') + key,
                                       'SUPER + F7']}
                self.run_setup()
                self.assertIn('o.bind("SUPER + F7"', self.bindings.read_text())
                if mask == 64 and key == 'N':
                    self.assertIn('SUPER + ALT + F7', self.bindings.read_text())

    def test_helper_path_with_spaces_and_shell_characters(self):
        folder = self.root / "plugin 'quoted' $literal"
        folder.mkdir()
        helper = folder / 'taskspaces'
        shutil.copy2(SCRIPT, helper)
        (self.root / 'mock.json').write_text(json.dumps(self.cfg))
        result = subprocess.run(['/bin/bash', str(helper), 'setup'], env=self.env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(START, self.bindings.read_text())
        self.assertFalse((self.root / 'literal').exists())

    def test_invalid_flags(self):
        self.run_setup('--remove', '--dry-run', expected=2)
        self.unchanged()

    def support_browser(self):
        self.desktop.write_text('[Desktop Entry]\nExec=chromium %U\n')

    def core_block(self):
        self.desktop.write_text('[Desktop Entry]\nExec=firefox %U\n')
        self.bindings.write_text(ORIGINAL)
        self.cfg = {'choices': ['Yes']}
        self.run_setup()
        text = self.bindings.read_text()
        (self.root / 'events.jsonl').unlink()
        for backup in self.backups():
            backup.unlink()
        self.cfg = {}
        return text

    def test_browser_accepted_exact_block_consent_notification_and_remove(self):
        self.support_browser()
        self.cfg['choices'] = ['Add a "new browser window here" shortcut', 'Yes']
        result = self.run_setup()
        browser_line = 'o.bind("SUPER + ALT + B", "New browser window here", taskspaces_bin .. " browser")\n'
        block = '\n'.join([START, 'local taskspaces_bin = ' + json.dumps(str(SCRIPT)),
                           'o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")',
                           'o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskspaces_bin .. " send --silent")',
                           'o.bind("SUPER + D", "Finish task", taskspaces_bin .. " finish")', '']) + browser_line + END + '\n'
        self.assertEqual(self.bindings.read_text(), ORIGINAL + block)
        menus = self.non_go_menus()
        self.assertEqual(menus[0][0], 'Browser windows can jump back to where the browser was first opened')
        self.assertEqual(menus[0][1:3], ['󰀄\tAdd a "new browser window here" shortcut\tSuper+Alt+B',
                                        '󰁍\tNot now\tyou can run taskspaces browser any time'])
        for label in ('Super+N send', 'Super+Alt+N silent', 'Super+D finish', 'Super+Alt+B browser'):
            self.assertIn(label, menus[1][1])
        for menu in menus:
            for row in menu[1:-3]:
                self.assertLessEqual(len(row.split('\t')[1]), 50)
        self.assertIn('Super+Alt+B opens a new browser window here', result.stderr)
        self.assertEqual(self.backups()[0].read_text(), ORIGINAL)
        self.cfg['choices'] = ['Remove']
        self.run_setup('--remove')
        self.assertEqual(self.bindings.read_text(), ORIGINAL)

    def test_browser_declined_or_cancelled_still_sets_up_core(self):
        self.support_browser()
        for choice in ('Not now', 'cancel'):
            with self.subTest(choice=choice):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'choices': [choice, 'Yes']}
                self.run_setup()
                self.assertIn(' finish")', self.bindings.read_text())
                self.assertNotIn(' browser")', self.bindings.read_text())

    def test_unsupported_browser_step_not_offered(self):
        for browser in ('firefox', 'zen', 'other-browser'):
            with self.subTest(browser=browser):
                self.desktop.write_text('[Desktop Entry]\nExec=' + browser + ' %U\n')
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'choices': ['Yes']}
                self.run_setup()
        menus = self.non_go_menus()
        self.assertEqual(len(menus), 3)
        self.assertTrue(all(menu[0] == 'Add Taskspaces shortcuts?' for menu in menus))

    def test_browser_conflict_alternative_own_key_and_skip(self):
        self.support_browser()
        # These stock keys are present on the target Omarchy, including
        # conditional defaults: none may be suggested as a free alternative.
        (self.stock / 'applications.lua').write_text(
            'o.bind("SUPER + ALT + RETURN", "Tmux", "terminal-tmux")\n'
            'o.bind("SUPER + CTRL + RETURN", "Another application", "terminal-app")\n'
            'o.bind("SUPER + SHIFT + B", "Browser", "browser")\n'
            'o.bind("SUPER + SHIFT + RETURN", "Browser", "browser")\n')
        for choice, key in (('Alternative', 'SUPER + ALT + W'),
                            ('Pick', 'SUPER + F8'), ('Skip', None)):
            with self.subTest(choice=choice):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': [bind(72, 'B')],
                            'choices': ['Add a "new browser window here" shortcut', choice, 'Yes'],
                            'inputs': ['SUPER + F8']}
                self.run_setup()
                text = self.bindings.read_text()
                if key:
                    self.assertIn('o.bind("' + key + '", "New browser window here"', text)
                else:
                    self.assertNotIn(' browser")', text)
                self.assertNotIn('o.bind("SUPER + SHIFT + RETURN"', text)

    def test_browser_default_with_stock_defaults_needs_no_conflict_menu(self):
        self.support_browser()
        (self.stock / 'applications.lua').write_text(
            'o.bind("SUPER + ALT + RETURN", "Tmux", "terminal-tmux")\n'
            'o.bind("SUPER + CTRL + RETURN", "Another application", "terminal-app")\n'
            'o.bind("SUPER + SHIFT + RETURN", "Browser", "browser")\n'
            'o.bind("SUPER + SHIFT + B", "Browser", "browser")\n'
            'o.bind("SUPER + CTRL + B", "Bluetooth", "bluetooth")\n')
        self.cfg['choices'] = ['Add a "new browser window here" shortcut', 'Yes']
        self.run_setup()
        menus = self.non_go_menus()
        self.assertEqual([menu[0] for menu in menus],
                         ['Browser windows can jump back to where the browser was first opened',
                          'Add Taskspaces shortcuts?'])
        self.assertIn('\tSuper+Alt+B', menus[0][1])
        self.assertIn('o.bind("SUPER + ALT + B", "New browser window here"', self.bindings.read_text())

    def test_browser_alternatives_are_ordered_and_stop_after_two(self):
        self.support_browser()
        for taken, expected in (([bind(72, 'B')], 'SUPER + ALT + W'),
                                ([bind(72, 'B'), bind(72, 'W')], 'SUPER + ALT + C'),
                                ([bind(72, 'B'), bind(72, 'W'), bind(72, 'C')], None)):
            with self.subTest(expected=expected):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': taken,
                            'choices': ['Add a "new browser window here" shortcut',
                                        'Alternative' if expected else 'Skip', 'Yes']}
                self.run_setup()
                if expected:
                    self.assertIn('o.bind("' + expected + '", "New browser window here"', self.bindings.read_text())
                else:
                    self.assertNotIn(' browser")', self.bindings.read_text())
                    menu = self.non_go_menus()[-2]
                    self.assertFalse(any('Use ' in row for row in menu[1:]))

    def test_browser_keys_are_free_in_installed_stock_bindings(self):
        folder = Path('/usr/share/omarchy/default/hypr/bindings')
        files = sorted(folder.glob('*.lua'))
        if not files:
            self.skipTest('Omarchy stock bindings are not installed')
        for file in files:
            (self.stock / file.name).write_bytes(file.read_bytes())
        self.support_browser()
        # Only the browser step: unrelated future stock changes to the three
        # core defaults must not obscure whether these browser keys are free.
        core = ORIGINAL + START + '\n' + MANUAL + END + '\n'
        self.bindings.write_text(core)
        for taken, expected in (([], 'SUPER + ALT + B'),
                                ([bind(72, 'B')], 'SUPER + ALT + W'),
                                ([bind(72, 'B'), bind(72, 'W')], 'SUPER + ALT + C')):
            with self.subTest(expected=expected):
                (self.root / 'events.jsonl').unlink(missing_ok=True)
                self.cfg = {'binds': taken,
                            'choices': ['Add a "new browser window here" shortcut'] +
                                       (['Alternative'] if taken else []) + ['Yes']}
                result = self.run_setup('--dry-run')
                self.assertIn('o.bind("' + expected + '", "New browser window here"', result.stdout)
                self.assertEqual(len(self.non_go_menus()), 3 if taken else 2)
                self.unchanged(core)

    def test_browser_live_conflict_rejects_taken_custom_key(self):
        self.support_browser()
        self.cfg = {'binds': [bind(72, 'B'), bind(64, 'F8')],
                    'choices': ['Add a "new browser window here" shortcut', 'Pick', 'Yes'],
                    'inputs': ['SUPER + N', 'SUPER + F8', 'SUPER + F9']}
        self.run_setup()
        self.assertIn('SUPER + F9', self.bindings.read_text())
        self.assertEqual(len(self.events('omarchy-menu-input')), 3)

    def test_upgrade_only_offers_browser_preserves_core_and_surroundings(self):
        core = self.core_block() + '-- Keep this tail\n'
        self.bindings.write_text(core)
        self.support_browser()
        self.cfg['choices'] = ['Add a "new browser window here" shortcut', 'Yes']
        self.run_setup()
        expected = core.replace(END, 'o.bind("SUPER + ALT + B", "New browser window here", taskspaces_bin .. " browser")\n' + END)
        self.assertEqual(self.bindings.read_text(), expected)
        self.assertEqual(self.backups()[0].read_text(), core)
        menus = self.non_go_menus()
        self.assertEqual(len(menus), 2)
        self.assertIn('Super+Alt+B browser', menus[1][1])
        self.assertNotIn('Super+N send', menus[1][1])
        self.assertEqual(self.cfg['reload_files'], [expected])

    def test_upgrade_declined_or_conflict_skipped_writes_nothing(self):
        core = self.core_block()
        self.support_browser()
        for choices, live in ((['Not now'], []),
                              (['Add a "new browser window here" shortcut', 'Skip'], [bind(72, 'B')])):
            self.cfg = {'choices': choices, 'binds': live}
            self.run_setup()
            self.unchanged(core)

    def test_browser_already_managed_hand_pasted_or_live_reports_key(self):
        self.support_browser()
        browser_line = 'o.bind("SUPER + F8", "New browser window here", taskspaces_bin .. " browser")\n'
        for text, live, key in (
                (START + '\n' + MANUAL + browser_line + END + '\n', [], 'SUPER + F8'),
                (MANUAL + browser_line, [], 'SUPER + F8'),
                ('o.bind("SUPER + F9", "Browser", "taskspaces browser")\n', [], 'SUPER + F9'),
                (ORIGINAL, [legacy_bind(64, 'F10', arg=str(SCRIPT) + ' browser')], 'Super+F10'),
                (ORIGINAL, [bind(64, 'F11', description='New browser window here')], 'Super+F11')):
            with self.subTest(key=key, text=text):
                self.bindings.write_text(text)
                self.cfg = {'binds': live}
                result = self.run_setup()
                self.assertIn('Already set up', result.stderr)
                self.assertIn(key, result.stderr)
                self.unchanged(text)
        self.assertEqual(self.non_go_menus(), [])

    def test_browser_dry_run_including_upgrade_writes_nothing(self):
        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade):
                core = self.core_block() if upgrade else ORIGINAL
                self.support_browser()
                self.cfg = {'choices': ['Add a "new browser window here" shortcut', 'Yes']}
                result = self.run_setup('--dry-run')
                self.assertIn(' browser")', result.stdout)
                self.unchanged(core)

    def test_browser_verification_failure_rolls_back_new_and_upgraded_block(self):
        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade):
                self.desktop.write_text('[Desktop Entry]\nExec=firefox %U\n')
                core = self.core_block() if upgrade else ORIGINAL
                self.support_browser()
                self.cfg = {'choices': ['Add a "new browser window here" shortcut', 'Yes'], 'missing_browser': True}
                result = self.run_setup(expected=1)
                self.assertIn('restored and reloaded', result.stderr)
                self.assertEqual(self.bindings.read_text(), core)
                self.assertEqual(self.backups()[-1].read_text(), core)
                self.assertEqual(self.cfg['reloaded'], 2)

    def test_browser_key_taken_during_final_consent_changes_nothing(self):
        self.support_browser()
        self.cfg = {'choices': ['Add a "new browser window here" shortcut', 'Yes'],
                    'take_on_menu': bind(72, 'B')}
        result = self.run_setup(expected=1)
        self.assertIn('just taken', result.stderr)
        self.unchanged()

    # The shape real Hyprland reports for a Lua config: dispatcher __lua, arg is an id,
    # the label is in description. Earlier mocks reported exec with the command in arg,
    # so setup rolled back a correct install on every real desktop.
    def test_lua_config_shortcuts_are_recognised_after_reload(self):
        result = self.run_setup()
        self.assertIn('Ready:', result.stderr)
        self.assertNotIn('did not load', result.stderr)
        self.assertEqual(self.cfg['reloaded'], 1)
        self.assertIn(START, self.bindings.read_text())

    def test_lua_config_browser_shortcut_is_recognised_after_reload(self):
        self.support_browser()
        self.cfg['choices'] = ['Add a "new browser window here" shortcut', 'Yes']
        result = self.run_setup()
        self.assertIn('Super+Alt+B opens a new browser window here', result.stderr)
        self.assertEqual(self.cfg['reloaded'], 1)

    def test_legacy_exec_shortcuts_are_still_recognised(self):
        self.support_browser()
        self.cfg = {'legacy_exec': True, 'choices': ['Add a "new browser window here" shortcut', 'Yes']}
        result = self.run_setup()
        self.assertIn('Ready:', result.stderr)
        self.assertEqual(self.cfg['reloaded'], 1)
        self.cfg['choices'] = ['Remove']
        self.run_setup('--remove')
        self.assertEqual(self.bindings.read_text(), ORIGINAL)

    def test_lua_shortcut_with_a_different_description_is_not_ours(self):
        for stale in ('wrong_helper', 'missing_loaded'):
            with self.subTest(stale=stale):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {stale: True, 'choices': ['Yes']}
                self.assertIn('did not load every selected', self.run_setup(expected=1).stderr)
                self.assertEqual(self.bindings.read_text(), ORIGINAL)

    def test_remove_checks_the_live_shortcuts_for_real(self):
        for shape in ('lua', 'legacy'):
            with self.subTest(shape=shape):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'choices': ['Yes']}
                self.run_setup()
                before = self.bindings.read_bytes()
                if shape == 'lua':
                    stale = [bind(64, 'N', 'Send window to task'), bind(64, 'D', 'Finish task')]
                else:
                    stale = [legacy_bind(64, 'n', arg=str(SCRIPT) + ' send')]
                self.cfg = {'choices': ['Remove'], 'stale_binds': stale, 'legacy_exec': shape == 'legacy'}
                result = self.run_setup('--remove', expected=1)
                self.assertIn('still shows a removed Taskspaces shortcut', result.stderr)
                self.assertIn('restored and reloaded', result.stderr)
                self.assertEqual(self.bindings.read_bytes(), before)

    def test_remove_ignores_other_shortcuts_on_the_same_keys(self):
        self.run_setup()
        # Same description on a different key, or another label on the same key, is not ours.
        other = [bind(64, 'E', 'Finish task'), bind(65, 'N', 'Send window to task'),
                 bind(64, 'N', 'Something else')]
        self.cfg = {'choices': ['Remove'], 'stale_binds': other}
        self.run_setup('--remove')
        self.assertEqual(self.bindings.read_text(), ORIGINAL)

    def test_live_browser_shortcut_detection_for_lua_config(self):
        self.support_browser()
        for live, found in (([bind(64, 'F11', 'New browser window here')], True),
                            ([bind(64, 'F11', 'Browser (new window here)')], False),
                            ([bind(64, 'F11', 'Finish task')], False)):
            with self.subTest(live=live):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': live, 'choices': ['Not now', 'Yes']}
                result = self.run_setup()
                self.assertEqual('Already set up' in result.stderr, found)

    def test_is_ours_predicate(self):
        ours = setup_namespace()['is_ours']
        helper = Path('/opt/plugin/bin/taskspaces')
        lua = bind(72, 'N', 'Send window to task (stay here)')
        self.assertTrue(ours(lua, helper, 'send --silent', (72, 'N')))
        self.assertTrue(ours(lua, helper, 'send --silent'))
        self.assertFalse(ours(lua, helper, 'send --silent', (72, 'M')))
        self.assertFalse(ours(lua, helper, 'send --silent', (64, 'N')))
        self.assertFalse(ours(lua, helper, 'send', (72, 'N')))
        self.assertFalse(ours(dict(lua, description=''), helper, 'send --silent', (72, 'N')))
        self.assertFalse(ours(dict(lua, description=None), helper, 'send --silent', (72, 'N')))
        self.assertFalse(ours({k: v for k, v in lua.items() if k != 'description'}, helper, 'send --silent'))
        self.assertFalse(ours(dict(lua, dispatcher='exec', arg='1'), helper, 'send --silent', (72, 'N')))
        legacy = legacy_bind(64, 'n', arg="/opt/plugin/bin/taskspaces send")
        self.assertTrue(ours(legacy, helper, 'send', (64, 'N')))
        self.assertFalse(ours(legacy, helper, 'finish', (64, 'N')))
        self.assertFalse(ours(dict(legacy, arg='/other/taskspaces send'), helper, 'send', (64, 'N')))
        self.assertFalse(ours(dict(legacy, arg="'unterminated send"), helper, 'send', (64, 'N')))
        spaced = legacy_bind(64, 'n', arg="'/opt/my plugin/bin/taskspaces' send")
        self.assertTrue(ours(spaced, Path('/opt/my plugin/bin/taskspaces'), 'send', (64, 'N')))
        # A legacy match needs the right command even when the description is ours.
        self.assertFalse(ours(dict(legacy, description='Send window to task', arg='launcher'),
                              helper, 'send', (64, 'N')))

    def test_every_key_setup_accepts_matches_what_hyprland_reports(self):
        space = setup_namespace()
        parse_key, bind_key = space['parse_key'], space['bind_key']
        names = (list('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') + ['F%d' % n for n in range(1, 36)] +
                 'RETURN SPACE TAB ESCAPE LEFT RIGHT UP DOWN HOME END PAGE_UP PAGE_DOWN INSERT DELETE BACKSPACE'.split())
        for name in names:
            for mods, mask in (('SUPER + ALT', 72), ('SUPER + CTRL + SHIFT', 69), ('ALT', 8)):
                chosen = parse_key(mods + ' + ' + name)
                self.assertEqual(chosen[0], mask)
                # Hyprland reports the key as written; stock files spell some of them
                # in title case or lower case.
                for spelling in (name, name.lower(), name.title()):
                    with self.subTest(name=name, spelling=spelling):
                        self.assertEqual(bind_key(bind(mask, spelling)), chosen)

    def test_masks_match_the_captured_modifier_bits(self):
        mods = setup_namespace()['MODS']
        self.assertEqual((mods['SUPER'], mods['SHIFT'], mods['CTRL'], mods['ALT']), (64, 1, 4, 8))
        self.assertEqual(setup_namespace()['parse_key']('SUPER + ALT + RETURN'), (72, 'RETURN'))

    def test_keycode_shortcuts_reserve_digit_keys(self):
        # Hyprland reports a code:NN shortcut with an empty key and no usable keycode,
        # so a digit under the same modifiers may already be taken.
        self.cfg = {'binds': [bind(64, '', 'Switch to workspace 1'), bind(64, 'D')],
                    'choices': ['Pick', 'Yes'], 'inputs': ['SUPER + 3', 'SUPER + SHIFT + 3', 'SUPER + F6']}
        result = self.run_setup()
        self.assertIn('SUPER + SHIFT + 3', self.bindings.read_text())
        self.assertEqual(len(self.events('omarchy-menu-input')), 2)
        self.assertIn('already used', result.stderr)

    def test_alias_key_names_are_the_same_key(self):
        space = setup_namespace()
        parse_key, bind_key = space['parse_key'], space['bind_key']
        for alias, canonical in (('ESC', 'ESCAPE'), ('Prior', 'PAGE_UP'), ('Next', 'PAGE_DOWN')):
            self.assertEqual(bind_key(bind(64, alias)), parse_key('SUPER + ' + canonical))
            self.assertEqual(parse_key('SUPER + ' + alias), parse_key('SUPER + ' + canonical))

    def test_non_newline_file_is_separated_from_block(self):
        self.bindings.write_text('-- no final newline')
        self.run_setup()
        self.assertTrue(self.bindings.read_text().startswith('-- no final newline\n' + START))
        self.assertEqual(self.backups()[0].read_text(), '-- no final newline')


if __name__ == '__main__':
    unittest.main()
