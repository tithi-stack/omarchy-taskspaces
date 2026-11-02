# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added

- **First workspace for tasks** widget setting (`firstTaskWorkspace`, default 6; integers 1 to 50, invalid values fall back to 6). New single-screen tasks start there; two-screen tasks prefer pairs 6–7, 8–9 and onward, preserving all existing reservations. Workspaces 1 to 5 stay yours unless you adopt one or lower the setting; open tasks keep their numbers, and setting 1 restores the previous allocation.
- Read-only `taskspaces setup --check` lists settings and workspace reservation reasons, including existing Hyprland rules such as those left by Omarchy's Super+L toggle. Those numbers are skipped for two-screen tasks because Hyprland cannot take just the layout out of a merged rule. Omarchy's stock bar draws only up to workspace 10; a number above 5 usually means a task or a window you put there yourself.
- Start and send windows to named task workspaces. Accept a name suggested from the window title, type your own, name the current numbered workspace, or rename a task. Optional `send --silent` moves a window without following it.
- Go to tasks by name from the task menu, `taskspaces go`, or a click on the bar label. Task lists show window summaries and put recently used tasks first. The bar shows task names, with an optional window title outside tasks. The widget itself never focuses, moves or closes a window; a click opens the Go-to-task list, and focusing happens only when you pick a row.
- Finish tasks by closing their windows or keeping them and returning them to their starting workspace. Close uses normal app close requests and leaves unfinished tasks available when windows stay open. Forget a stuck task from its recovery menu or `taskspaces forget`, leaving every window where it is.
- Set up two shortcuts, Super+N for the task menu and Super+D for Finish, with conflict checks, previews, consent, backups and verified rollback. Remove the managed bindings with `setup --remove`; preview without writing with `setup --dry-run`. Direct Go, silent send and browser bindings are optional manual snippets. `taskspaces browser` opens a new Chromium, Chrome, Brave, Brave Origin or Edge window with a saved profile.
- Experimental two-screen tasks, off by default in the widget settings. When enabled, new tasks use one workspace per screen and share one name and menu entry. Go switches both screens, can combine windows after unplugging a screen, and restores their placement after reconnecting. Finish reviews both screens together.

[0.1.0]: https://github.com/tithi-stack/omarchy-taskspaces/releases/tag/v0.1.0
