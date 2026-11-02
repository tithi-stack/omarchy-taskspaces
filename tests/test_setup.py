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
        if (self.bin / 'hyprctl').exists():
            resolved = subprocess.check_output(['/bin/bash', '-c', 'command -v hyprctl'], env=self.env, text=True).strip()
            self.assertEqual(Path(resolved), self.bin / 'hyprctl')
        result = subprocess.run(['/bin/bash', str(SCRIPT), 'setup', *args], env=self.env,
                                capture_output=True, text=True, timeout=15, stdin=stdin)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.cfg = json.loads((self.root / 'mock.json').read_text())
        return result

    def events(self, command=None):
        file = self.root / 'events.jsonl'
        items = [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []
        return [args for cmd, args in items if command is None or cmd == command]

    def menus(self):
        return self.events('omarchy-menu-select')

    def backups(self):
        return list((self.root / 'state/taskspaces/backups').glob('bindings.lua.*'))

    def unchanged(self, original=ORIGINAL):
        self.assertEqual(self.bindings.read_text(), original)
        self.assertEqual(self.backups(), [])
        self.assertNotIn(['reload'], self.events('hyprctl'))

    def test_setup_offers_only_two_keys_even_with_supported_browser(self):
        self.support_browser()
        self.run_setup()
        text = self.bindings.read_text()
        self.assertEqual(text.count('o.bind('), ORIGINAL.count('o.bind(') + 2)
        self.assertNotIn('send --silent', text)
        self.assertNotIn(' go")', text)
        self.assertNotIn(' browser")', text)
        self.assertEqual([m[0] for m in self.events('omarchy-menu-select')], ['Add Taskspaces shortcuts?'])
        self.assertEqual(self.events('omarchy-cmd-default-browser'), [])

    def test_rerun_preserves_five_key_block_until_explicit_removal(self):
        block = (START + '\n' + MANUAL +
                 'o.bind("SUPER + ALT + T", "Go to task", taskspaces_bin .. " go")\n' +
                 'o.bind("SUPER + ALT + B", "New browser window here", taskspaces_bin .. " browser")\n' + END + '\n')
        original = ORIGINAL + block
        self.bindings.write_text(original)
        self.assertIn('Existing shortcuts were left unchanged', self.run_setup().stderr)
        self.unchanged(original)
        self.assertEqual(self.events('omarchy-menu-select'), [])
        self.cfg = {'choices': ['Remove']}
        self.run_setup('--remove')
        self.assertEqual(self.bindings.read_text(), ORIGINAL)
        self.cfg = {'choices': ['Yes']}
        self.run_setup()
        self.assertEqual(self.bindings.read_text().count('o.bind('), ORIGINAL.count('o.bind(') + 2)

    def test_free_yes_exact_block_backup_atomic_permissions_and_idempotency(self):
        inode = self.bindings.stat().st_ino
        result = self.run_setup()
        block = '\n'.join([START, 'local taskspaces_bin = ' + json.dumps(str(SCRIPT)),
                           'o.bind("SUPER + N", "Send window to task", taskspaces_bin .. " send")',
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
        menus = self.menus()
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
        for mask, key, expected in ((64, 'n', 'SUPER + SHIFT + T'),
                                    (64, 'd', 'SUPER + SHIFT + D')):
            with self.subTest(mask=mask, key=key):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': [bind(mask, key)], 'choices': ['Alternative', 'Yes']}
                result = self.run_setup()
                self.assertIn('o.bind("' + expected + '"', self.bindings.read_text())
                self.assertIn('already used by "Open launcher"', self.menus()[-2][0])
                if mask == 64 and key == 'n':
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
        menu = self.menus()[-2]
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

    def test_skip_send_still_offers_finish(self):
        self.cfg = {'binds': [bind(64, 'N')], 'choices': ['Skip', 'Yes']}
        result = self.run_setup()
        self.assertNotIn(' send', self.bindings.read_text())
        self.assertIn('Super+D finishes', result.stderr)
        self.assertNotIn('Super+N sends', result.stderr)

    def test_skip_all_writes_nothing(self):
        self.cfg = {'binds': [bind(64, 'N'), bind(64, 'D')], 'choices': ['Skip', 'Skip']}
        self.run_setup()
        self.unchanged()


    def test_conflict_title_falls_back_and_sanitizes(self):
        self.cfg = {'binds': [bind(64, 'D', description='\n"Bad\x1b\tname"')], 'choices': ['Skip', 'No']}
        self.run_setup()
        self.assertEqual(self.menus()[0][0], 'Super+D is already used by "Bad name"')
        # A Lua shortcut has no command text to show: arg is only an id.
        self.cfg = {'binds': [bind(64, 'D', description='')], 'choices': ['Skip', 'No']}
        self.run_setup()
        self.assertEqual(self.menus()[-2][0],
                         'Super+D is already used by "another shortcut"')
        self.cfg = {'binds': [legacy_bind(64, 'D', description='')], 'choices': ['Skip', 'No']}
        self.run_setup()
        self.assertIn('exec launcher', self.menus()[-2][0])

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
                os.write(master, answer)
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
        for mask, key in ((64, 'N'), (64, 'D')):
            with self.subTest(mask=mask, key=key):
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'binds': [bind(mask, key)], 'choices': ['Pick', 'Yes'],
                            'inputs': ['SUPER + ?', 'SUPER + ' + ('ALT + ' if mask == 72 else '') + key,
                                       'SUPER + F7']}
                self.run_setup()
                self.assertIn('o.bind("SUPER + F7"', self.bindings.read_text())

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

    def test_unsupported_browser_step_not_offered(self):
        for browser in ('firefox', 'zen', 'other-browser'):
            with self.subTest(browser=browser):
                self.desktop.write_text('[Desktop Entry]\nExec=' + browser + ' %U\n')
                self.bindings.write_text(ORIGINAL)
                self.cfg = {'choices': ['Yes']}
                self.run_setup()
        menus = self.menus()
        self.assertEqual(len(menus), 3)
        self.assertTrue(all(menu[0] == 'Add Taskspaces shortcuts?' for menu in menus))

    # The shape real Hyprland reports for a Lua config: dispatcher __lua, arg is an id,
    # the label is in description. Earlier mocks reported exec with the command in arg,
    # so setup rolled back a correct install on every real desktop.
    def test_lua_config_shortcuts_are_recognised_after_reload(self):
        result = self.run_setup()
        self.assertIn('Ready:', result.stderr)
        self.assertNotIn('did not load', result.stderr)
        self.assertEqual(self.cfg['reloaded'], 1)
        self.assertIn(START, self.bindings.read_text())


    def test_legacy_exec_shortcuts_are_still_recognised(self):
        self.support_browser()
        self.cfg = {'legacy_exec': True, 'choices': ['Yes']}
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
