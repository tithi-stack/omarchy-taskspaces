# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Send rows read `Start task "<name>"`, `Start task with my own name…`, and `Turn workspace S into a task…`. Grey descriptions explain the suggested name, Chrome's whole-window scope, and windows staying in place. `Send to:` and `Move to:` spell out `workspace <id>` in grey.
- Finish uses `Close 1 window and finish` / `Close N windows and finish` and `Keep 1 window and finish` / `Keep N windows and finish`. Keep shows `returns to workspace S · nothing is closed`, or `stays in workspace S · nothing is closed` for a task made from a numbered workspace.
- Menu icons use Omarchy's Nerd Font: 󰐗 suggested name, 󰏫 type or rename, 󰉗 name the current workspace, 󰉒 send or move, 󰖭 close, 󰐃 keep, and 󰁍 cancel.
- Suggested names stay within 35 characters, including duplicate-name numbers, so the first row always reads `Start task "<name>"`. Typed names keep their 40-character limit.
- Close waits up to 30 seconds, stopping early only after 10 seconds with no windows closing and no new window appearing.

### Fixed

- Finish refreshes the task's windows after the menu, includes newly opened windows, and skips windows closed by hand. Windows disappearing during dispatch no longer interrupt cleanup or the success notification.
- Tasks started from special workspaces record workspace 1 as their return destination. Tasks remember the starting workspace's number and name; if it disappears, changes name, or becomes another task, kept windows return to workspace 1. If workspace 1 also belongs to a task or has a custom name, they use the lowest unused workspace instead, and focus follows them.
- Quotes and backslashes are removed from fallback app names before they appear in task labels, the finish app summary, or prompts.
- Digit-only task names get a `Task ` prefix, and duplicate checks account for numbered workspaces.

## [0.1.0] - 2026-10-30

Initial public release. Target: Omarchy Quattro (4.0.0.alpha).

### Added

- `taskspaces send`: moves the focused window to a named task workspace. The name is suggested from the window title.
- `taskspaces send --silent`: the same, without following the window.
- `taskspaces finish`: closes the task's windows or moves them back, after a confirmation menu.
- `taskspaces --help` and `taskspaces --version`.
- Bar widget that shows the task name on a task workspace and the window title elsewhere.
- Documentation: README, how-it-works page, security policy, and contributing guide.

[Unreleased]: https://github.com/tithi-stack/omarchy-taskspaces/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tithi-stack/omarchy-taskspaces/releases/tag/v0.1.0
