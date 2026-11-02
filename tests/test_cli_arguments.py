"""Check command arguments at the real helper/compositor boundary, using mocks."""
import ast
import inspect
import json
import os
import re
import runpy
import subprocess
import unittest
from unittest.mock import patch

import test_taskspaces as tasks


class CliArgumentTests(unittest.TestCase):
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
                pair.new(5, '--task -j --help', 2, '2', incoming, True, False)
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
            elif command in ('omarchy-notification-send', 'notify-send'):
                positional = args[2:] if args[:1] == ['-g'] else args
                self.assertEqual(positional[0], 'taskspaces')
                self.assertFalse(positional[1].startswith('-'), args)
