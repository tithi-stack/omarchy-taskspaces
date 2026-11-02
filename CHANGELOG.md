# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- The send key can name an empty numbered workspace or rename an empty task, with navigation when other tasks exist and a warning when leaving it empty would lose its name.

## [0.1.0] - Unreleased

### Added

- Send menu groups window-moving rows before navigation and workspace naming, with explicit task destinations and a description on every row; Move includes empty plain destinations in the bar’s always-show range and hides when none are available.

- Task choices use names and window summaries, ordered by last use; plain workspaces have a separate window-summary list.
- `taskspaces go` and the send menu's **Go to a task…** list return to a task without moving a window; send with no focused window opens the same list.
- Setup offers an optional **Go to task** shortcut with consent, conflict checks, backups, verification, preview and removal, including upgrades of existing managed bindings.
- Task records accept an optional `used` time, updated on start, send-to and Go-to; task notifications use names.

- `taskspaces send`: moves the focused window to a named task workspace. Names come from the window title or a prompt; the send menu also supports naming the current workspace and renaming a task.
- `taskspaces send --silent`: sends without following the window.
- Suggested names preserve ordinary words and file names, omit IDs and status or shell words, and use the last component of terminal paths. Foot is labelled Terminal. Suggested names have a shorter length limit than typed names so the start row fits the menu.
- Send menus explain suggested names, Chrome's whole-window scope, and windows staying in place. Finish menus offer Close, Keep and Cancel, with the return destination shown before choosing.
- `taskspaces finish`: closes the task's windows or moves them back after a confirmation menu. Close sends normal close requests and waits for apps to respond, stopping when apps stop closing windows and no new window appears.
- `taskspaces setup`: consented shortcut setup with conflict alternatives, previews, backups, verified reload and rollback; `--remove` undoes its managed block and `--dry-run` prints without writing. Send alternatives start with `Super+Shift+T`, then `Super+Shift+H` and `Super+Shift+J` when free.
- `taskspaces browser`: opens a new window here with an existing Chromium, Chrome, Brave, Brave Origin or Edge profile; multiple profiles get a picker. It leaves Omarchy's browser launcher and stock shortcuts unchanged.
- Setup offers an optional new-browser-window shortcut for supported browsers: `Super+Alt+B` (B for browser), with `Super+Alt+W` then `Super+Alt+C` as free alternatives, and the same consent, backup and verified rollback. Existing managed blocks can add the browser line while preserving existing shortcuts. Preview and removal include the optional shortcut.
- `taskspaces --help` and `taskspaces --version`.
- Bar widget that shows the task name on a task workspace and the window title elsewhere, with a setting to hide the title outside tasks. Menu icons use Omarchy's Nerd Font, and the default task glyph is its layers glyph.
- Documentation: README with a task workflow and hero image, how-it-works page, shortcut recovery instructions, security policy, and contributing guide.

[Unreleased]: https://github.com/tithi-stack/omarchy-taskspaces/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tithi-stack/omarchy-taskspaces/releases/tag/v0.1.0
