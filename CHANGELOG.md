# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New tasks span two connected screens with one task identity, one menu row and a shared bar label; existing tasks and one-screen creation keep their current behavior.
- Go restores both task areas, recreates missing empty areas and reserves all member IDs. Task-owned runtime persistence rules avoid replacing configured rules and are disabled on Finish.
- Explicit Go after unplug merges task windows on the remaining screen; Go after reconnect restores recorded windows to their original areas with address/identity checks and retained recovery state on failure. Silent send preserves both visible workspaces.
- Paired Finish reviews both screens once, supports each area's safe return destination, and retains tasks on refused closes, new windows and partial failures.

- Left-click the bar label (task name or window title) to launch your own existing Go-to-task list, with a pointing-hand cursor and a **click for tasks** hover hint. The widget itself never focuses, moves or closes a window; focusing happens only when you pick a row.

### Fixed

- Start cleanup Lua with a statement so `hyprctl eval` does not parse a leading comment as a CLI flag; the compositor mock now rejects option-like eval/dispatch arguments.

- Prepare and activate a normal Send destination before moving its chosen window, retaining the window at its source if preparation fails. Silent Send remains one window move with unchanged visible workspaces.
- Release all owned member handles at Finish and orphaned handles at task refresh; recover a reused member still named by a dead record without moving or closing its windows. Paired allocation reuses eligible empty inactive numbered slots, preserving live windows, tasks and reservations.
- Keep paired Finish fallbacks on each member's connected output; accept a numeric name during owned workspace creation; skip closed or changed split-back entries while restoring the remaining windows.
- Refresh labels on debounced compositor events with a 30-second fallback instead of spawning Python every second on each bar.

- Bind task-owned persistence rules to their requested output before empty-area creation. Flush scheduled property refresh immediately, verify placement, and use a targeted move only for repair before activating each screen and its area. The mock now enforces rule bindings and unbound-rule snap-back. Go repairs half-built tasks from the first paired-screen build.
- Use readable task names with trailing markers for distinct native workspace names, so a bar still running the old widget never displays newly generated member jargon. Go migrates old generated names, and task rename updates both native names. Current labels continue showing the common task name on both screens.

- Receive bar-label clicks through the bar host’s root `triggerPress` hook; the inner MouseArea handles hover only. Ignore other mouse buttons and hide the tooltip before opening the list.

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
