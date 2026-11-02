"""Check command arguments at the real helper/compositor boundary, using mocks."""
import ast
import inspect
import json
import os
import re
import runpy
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_taskspaces as tasks


class CliArgumentTests(unittest.TestCase):
    def task_case(self):
        case = tasks.TaskTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def test_setup_check_needs_no_terminal_runtime_bindings_or_menu_tools(self):
        case = self.task_case()
        case.env.pop('XDG_RUNTIME_DIR')
        case.env['PATH'] = case.isolated_path('check-bin', ('python3', 'hyprctl'))
        case.env['TASKSPACES_BINDINGS_FILE'] = str(case.root / 'does-not-exist.lua')
        case.set_settings(first=8)
        result = case.run_task('setup', '--check')
        self.assertIn('First task workspace: 8', result.stdout)
        self.assertIn('Two-screen tasks: disabled (1 connected screens)', result.stdout)
        self.assertEqual(case.events('omarchy-menu-select'), [])
        self.assertEqual(list(case.state.iterdir()), [])
        self.assertTrue(all(a[0] in ('clients', 'monitors', 'workspaces', 'workspacerules')
                            for a in case.events('hyprctl')))

    def test_setup_check_rejects_extra_or_combined_flags_without_side_effects(self):
        case = self.task_case()
        for args in (('--check', '--remove'), ('--check', '--dry-run'), ('--check', '--check'),
                     ('--check', 'extra'), ('--remove', '--check')):
            with self.subTest(args=args):
                result = case.run_task('setup', *args, expected=2)
                self.assertIn('setup [--remove | --dry-run | --check]', result.stderr)
        self.assertEqual(case.events(), [])
        self.assertEqual(list(case.state.iterdir()), [])

    def test_help_describes_read_only_setup_check(self):
        case = self.task_case()
        result = case.run_task('--help')
        self.assertIn('setup [--remove | --dry-run | --check]', result.stdout)
        self.assertIn('setup --check', result.stdout)
        self.assertIn('read-only', result.stdout)
        self.assertEqual(case.events(), [])

    def test_mock_rejects_substring_routes_inside_lua_data(self):
        case = tasks.TaskTests()
        case.setUp()
        try:
            for verb in ('eval', 'dispatch'):
                for route in ('/--batch;eval os.exit();', '/hyprpaper', '/hyprsunset', '/instances'):
                    result = subprocess.run([str(case.root / 'bin/hyprctl'), verb,
                                             'hl.test("Notes' + route + '")'],
                                            env=case.env, text=True, capture_output=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('request route', result.stdout)
        finally:
            case.doCleanups()

    def test_hostile_titles_preserve_names_in_both_lua_quoters(self):
        lua = runpy.run_path(str(tasks.SCRIPT.with_name('taskspaces-members')))['lua']
        interpreter = next((path for name in ('lua', 'lua5.4', 'luajit')
                            if (path := shutil.which(name))), None)
        for name in ('Notes/--batch;eval os.exit();', 'a/5', 'Report/hyprpaper draft', 'Plain name'):
            for cls in (tasks.TaskTests, tasks.MultiMonitorTests):
                case = cls()
                case.setUp()
                try:
                    if cls is tasks.MultiMonitorTests:
                        case.screens()
                    case.cfg['activewindow']['title'] = name
                    case.cfg['select_first'] = True
                    case.run_task('send')
                    stored = [json.loads(p.read_text()) for p in case.state.glob('*.json')]
                    self.assertEqual(stored[0]['name'], name)
                    codes = [args[1] for args in case.events('hyprctl') if args[0] in ('eval', 'dispatch')]
                    self.assertTrue(codes)
                    for code in codes:
                        self.assertNotIn('/', code[1:])
                    literal = lua(name)
                    self.assertEqual(literal, '"' + name.replace('/', r'\047') + '"')
                    self.assertTrue(any(('name = ' + literal) in code for code in codes))
                    if interpreter:
                        result = subprocess.run([interpreter, '-'], input='io.write(' + literal + ')',
                                                text=True, capture_output=True, check=True)
                        self.assertEqual(result.stdout, name)
                    else:
                        # Exact emitted literals above prove the three-digit form;
                        # decoding is reasoned from Lua's decimal escape rules.
                        self.assertNotIn(r'\47', literal)
                finally:
                    case.doCleanups()

    def test_mock_rejects_option_like_eval_and_dispatch_arguments(self):
        case = tasks.TaskTests()
        case.setUp()
        try:
            for command in ('eval', 'dispatch'):
                for code in ('-- comment\nlocal a = 1', '-j'):
                    with self.subTest(command=command, code=code):
                        result = subprocess.run([str(case.root / 'bin/hyprctl'), command, code],
                                                env=case.env, text=True, capture_output=True)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('usage: hyprctl', result.stdout)
        finally:
            case.doCleanups()

    def test_every_hyprctl_code_builder_and_leading_dash_task_name_is_safe(self):
        helper = tasks.SCRIPT.with_name('taskspaces-members')
        namespace = runpy.run_path(str(helper))
        Pair = namespace['Pair']
        # Require actual execution of every helper Lua construction call site.
        expected = {node.lineno for node in ast.walk(ast.parse(helper.read_text()))
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self'
                    and node.func.attr == 'command'}
        visited = set()
        events = []

        def collect(case):
            events.extend(json.loads(line) for line in (case.root / 'events.jsonl').read_text().splitlines())
        original = Pair.command

        def checked(pair, kind, code, *args, **kwargs):
            visited.add(inspect.currentframe().f_back.f_lineno)
            self.assertFalse(code.startswith('-'), (kind, code))
            self.assertNotIn('/', code[1:], (kind, code))
            return original(pair, kind, code, *args, **kwargs)

        case = tasks.MultiMonitorTests()
        case.setUp()
        try:
            record = case.pair()
            # Configured nonpersistent rules force ensure's targeted repair path;
            # the orphan exercises cleanup, independently of task selection.
            case.cfg['workspaces'][-1]['monitor'] = 'eDP-1'
            case.cfg['workspaces'].append(tasks.real_workspace(77, 'taskspaces-99-2', 0))
            case.cfg['workspacerules'] = [dict(workspaceString=str(i), enabled=True) for i in (3, 4)]
            case.cfg['workspacerules'].append(dict(workspaceString='77', enabled=True,
                                                  persistent=True, defaultName='taskspaces-99-2'))
            case.cfg['owned_rules'] = {'77': 'taskspaces-99-2'}
            incoming = tasks.real_window('0x111', 'kitty', '--window', 2, '2')
            case.cfg['clients'].append(incoming)
            case.write_cfg()
            with patch.dict(os.environ, case.env), patch.object(Pair, 'command', checked):
                pair = Pair(False, case.state)
                pair.reconcile([record], pair.read('workspaces'))
                pair.go(record)
                # New rules, owned re-registration, arbitrary name data and both
                # focus fields; new() chooses its own lowest safe workspace ID.
                pair.new(5, 'Notes/--batch;eval os.exit();', 2, '2', incoming, True, False)
                new_file = next(p for p in case.state.glob('*.json') if p.name != '3.json')
                new_record = json.loads(new_file.read_text())
                pair.send(record, pair.window(incoming), True)
                pair.finish(record)  # reviewed close requests
                pair.finish(new_record)  # empty task, owned-rule release
            collect(case)
        finally:
            case.doCleanups()
        self.assertEqual(visited, expected, 'Every helper Lua construction site must be exercised')

        # Execute the legacy shell's move/rename/focus/close paths as well.
        scenarios = ('test_real_hyprland_shapes_work_for_send_and_finish',
                     'test_finish_close_plural_row_closes_every_window',
                     'test_empty_task_can_be_renamed_with_optional_go')
        for scenario in scenarios:
            case = tasks.TaskTests()
            case.setUp()
            try:
                getattr(case, scenario)()
                collect(case)
            finally:
                case.doCleanups()
        case = tasks.TaskTests()
        case.setUp()
        try:
            case.cfg['selection'] = 'Start task with my own name…\ttype a custom name · moves this window'
            case.cfg['input'] = '--task -j --help'
            case.run_task('send')
            self.assertEqual(case.events('omarchy-notification-send')[-1][-1],
                             'Started task "--task -j --help"')
            collect(case)
        finally:
            case.doCleanups()

        # All Bash dispatch expressions have a fixed prefix before any user data;
        # setup's compositor calls are fixed verbs, with no Lua code argument.
        script = tasks.SCRIPT.read_text()
        expressions = re.findall(r'\bdispatch\s+"([^"\n]*)', script)
        # A wrapper forwarding only $1/$name/${name} constructs no Lua. Its
        # actual code comes from the fixed-prefix callers and is checked below.
        forwarding = r'\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+|\{(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)\})'
        constructors = [code for code in expressions if not re.fullmatch(forwarding, code)]
        self.assertTrue(constructors)
        self.assertTrue(all(code.startswith('hl.dsp.') for code in constructors))
        setup_commands = re.findall(r"run\('hyprctl', '([^']+)'", script)
        self.assertEqual(set(setup_commands), {'binds', 'configerrors', 'reload'})
        self.assertTrue(events)
        for command, args in events:
            if command == 'hyprctl':
                self.assertFalse(args[0].startswith('-'))
                if args[0] in ('eval', 'dispatch'):
                    self.assertFalse(args[1].startswith('-'), args)
                    self.assertNotIn('/', args[1][1:], args)
            elif command in ('omarchy-notification-send', 'notify-send'):
                positional = args[2:] if args[:1] == ['-g'] else args
                self.assertEqual(positional[0], 'taskspaces')
                self.assertFalse(positional[1].startswith('-'), args)
