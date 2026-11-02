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
- Send, Go, Finish and Forget update task records in `$XDG_RUNTIME_DIR/taskspaces/` and a lock file, `$XDG_RUNTIME_DIR/taskspaces.lock`.
- The plugin never touches your Hyprland files unless you run `taskspaces setup` and choose Yes. Setup edits only `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` (or the test override `TASKSPACES_BINDINGS_FILE`). It preserves symlinks by updating their target and uses an atomic temporary replacement with the original permissions. It never replaces existing shortcuts.
- Before editing, setup backs up the original file to `${XDG_STATE_HOME:-$HOME/.local/state}/taskspaces/backups/`. Failed reload or verification restores the backup, unless another program edited the file during verification; then setup leaves those edits intact and gives the backup path for manual recovery. `setup --remove` asks for consent and removes only setup's marked block. Manual bindings are left alone; `setup --dry-run` writes nothing.
- Setup offers only the task-menu and Finish shortcuts. Re-running it preserves existing blocks, including older five-key blocks; removal includes all shortcuts inside the block. Optional manual bindings outside the block are left alone.
- Experimental two-screen tasks are off by default; when enabled, new tasks on two connected screens own two native workspaces. Turning the setting off leaves existing paired tasks usable. Go and send-and-follow activate both. When only one screen remains, the user's own Go selection merges the task's windows onto that screen, recording their addresses, identity fields and original areas before moving them. The next Go with both screens reconnecting splits those recorded windows back. There is no hot-plug listener or automatic layout change on connection events. Silent send moves only the selected window and leaves visible workspaces unchanged.
- Two-screen tasks use `hyprctl eval` to add temporary workspace rules to the live compositor, without editing config files. Taskspaces retains the Lua handles it creates and releases them on Finish, Forget or cleanup of a missing task record. It leaves configured rules without one of its handles alone. Hyprland can merge later settings for the same workspace into that same rule: releasing the handle can also disable a layout change made later, such as with Super+L, until the configuration reloads. A reload clears these temporary rules. Go recreates missing task workspaces; a conflicting live name stops the action with a recovery message.
- Forget releases rules and restores numbered workspace names before deleting the record. It never focuses, closes or moves windows or workspaces, and bypasses the name and screen checks that can leave Go or Finish stuck. It preserves names and rules still shared by another recorded task; a failed cleanup keeps the record for retry.
- Paired Finish checks the union of both task areas, including merged windows, and acts only on the confirmed addresses. New windows or dialogs retain the task. Merge/split verifies window identity and workspace before and after movement; failures keep metadata for retry or Forget. A closed or identity-changed split-back entry is skipped while the remaining windows restore. Normal Send activates and verifies the destination before moving the selected window, so a preparation failure leaves it at its source. Paired Keep fallbacks stay on the member's connected output. Runtime records include window titles and application metadata for recovery and are private to the current user/session.
- `taskspaces finish` can close windows. An app may ask you to save, and Taskspaces does not answer that prompt.
- The bar widget reads the workspace name, active window title and task records through a local helper on debounced workspace events, with a 30-second recovery poll. The helper may retire a fully absent, windowless task under the CLI lock and queue its rule/name cleanup for the next task action; it sends no compositor writes from a bar refresh. It maps its own screen's actual active workspace to the common task label and verifies the workspace name. It itself never focuses, moves or closes a window. A left click only launches your own Go-to-task list (`bin/taskspaces go`, resolved relative to the plugin); focusing happens only when you pick a row. The command is passed as an argument vector without interpreting the plugin path as shell code.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through a GitHub security advisory:

https://github.com/tithi-stack/omarchy-taskspaces/security/advisories/new

Go to **Security → Advisories → New draft advisory**. No response time is promised.

Problems in Omarchy, Hyprland, or the other tools Taskspaces calls belong with those projects.
