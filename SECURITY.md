# Security Policy

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## What Taskspaces does on your machine

- Runs local commands only: `hyprctl` (move, rename, focus, and close windows; setup reads bindings and config errors and reloads configuration), `jq`, `python3`, `flock`, Omarchy's menu commands, and a notification command (`omarchy-notification-send`, or `notify-send` as a fallback).
- Makes no network calls and does not use `sudo`.
- Window titles are untrusted input: task names are cleaned, quoted as Lua strings, and slashes become three-digit `\047` escapes so hyprctl cannot interpret names as request routes.
- `taskspaces browser` reads the default browser's desktop entry and `Local State` profile list read-only. It never writes browser files or calls Omarchy's browser launcher, handoff or focus helpers. It starts the supported browser with an explicit profile and `--new-window about:blank`, through `uwsm-app` when available. The launched browser retains its normal file and network behavior; Taskspaces itself makes no network requests.
- Send, Go and Finish write task records in `$XDG_RUNTIME_DIR/taskspaces/` and a lock file, `$XDG_RUNTIME_DIR/taskspaces.lock`.
- The plugin never touches your Hyprland files unless you run `taskspaces setup` and choose Yes. Setup edits only `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` (or the test override `TASKSPACES_BINDINGS_FILE`). It preserves symlinks by updating their target and uses an atomic temporary replacement with the original permissions. It never replaces existing shortcuts.
- Before editing, setup backs up the original file to `${XDG_STATE_HOME:-$HOME/.local/state}/taskspaces/backups/`. Failed reload or verification restores the backup, unless another program edited the file during verification; then setup leaves those edits intact and gives the backup path for manual recovery. `setup --remove` asks for consent and removes only setup's marked block. Manual bindings are left alone; `setup --dry-run` writes nothing.
- The optional browser shortcut uses the same consent, conflict checks, backups and verification. Re-running setup can add it to an existing managed block; removing that block also removes its browser line. Omarchy's stock browser shortcut is never replaced.
- New tasks on two connected screens own two native workspaces. Go and send-and-follow activate both. When only one screen remains, the user's own Go selection merges the task's windows onto that screen, recording their addresses, identity fields and original areas before moving them. The next Go with both screens reconnecting splits those recorded windows back. There is no hot-plug listener or automatic layout change on connection events. Silent send moves only the selected window and leaves visible workspaces unchanged.
- Paired tasks use `hyprctl eval` to register output-bound runtime persistent workspace rules and retain their Lua handles in a task-owned table. Configured numbered rules without an owned handle are never replaced. Task refresh disables orphaned owned handles, including stale generated defaults from a dead task whose workspace number was reused. It may restore that workspace's readable live-task name or ordinary number, preserving every window. Finish disables only the retained task-owned handles. No config file is edited; missing empty workspaces also recover from task records on Go. Placement registers the output binding and calls `hl.exec_scheduled_prop_refresh_immediately()` before verification; a targeted workspace move is only a repair. Go then focuses each recorded screen and area, restoring the initiating screen. Silent send never uses that visible repair. Native workspace names are readable task names with trailing markers where needed; Go migrates the prior generated names so a stale bar does not expose them after repair. Numeric IDs remain reserved when an area disappears; a mismatching live name stops the operation and retains the record.
- Paired Finish checks the union of both task areas, including merged windows, and acts only on the confirmed addresses. New windows or dialogs retain the task. Merge/split verifies window identity and workspace before and after movement; failures retain metadata for retry or inspection. A closed or identity-changed split-back entry is skipped while the remaining windows restore. Normal Send activates and verifies the destination before moving the selected window, so a preparation failure leaves it at its source. Paired Keep fallbacks stay on the member's connected output. Runtime records include window titles and application metadata for recovery and are private to the current user/session.
- `taskspaces finish` can close windows. An app may ask you to save, and Taskspaces does not answer that prompt.
- The bar widget reads the workspace name, active window title and task records through a read-only local helper on debounced workspace events, with a 30-second recovery poll. It maps its own screen's actual active workspace to the common task label and verifies the workspace name. It itself never focuses, moves or closes a window. A left click only launches your own Go-to-task list (`bin/taskspaces go`, resolved relative to the plugin); focusing happens only when you pick a row. The command is passed as an argument vector without interpreting the plugin path as shell code.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through a GitHub security advisory:

https://github.com/tithi-stack/omarchy-taskspaces/security/advisories/new

Go to **Security → Advisories → New draft advisory**. No response time is promised.

Problems in Omarchy, Hyprland, or the other tools Taskspaces calls belong with those projects.
