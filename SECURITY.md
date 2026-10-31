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
- Send and finish write task records in `$XDG_RUNTIME_DIR/taskspaces/` and a lock file, `$XDG_RUNTIME_DIR/taskspaces.lock`.
- The plugin never touches your Hyprland files unless you run `taskspaces setup` and choose Yes. Setup edits only `${XDG_CONFIG_HOME:-$HOME/.config}/hypr/bindings.lua` (or the test override `TASKSPACES_BINDINGS_FILE`). It preserves symlinks by updating their target and uses an atomic temporary replacement with the original permissions. It never replaces existing shortcuts.
- Before editing, setup backs up the original file to `${XDG_STATE_HOME:-$HOME/.local/state}/taskspaces/backups/`. Failed reload or verification restores the backup, unless another program edited the file during verification; then setup leaves those edits intact and gives the backup path for manual recovery. `setup --remove` asks for consent and removes only setup's marked block. Manual bindings are left alone; `setup --dry-run` writes nothing.
- `taskspaces finish` can close windows. An app may ask you to save, and Taskspaces does not answer that prompt.
- The bar widget only reads the workspace name from Hyprland.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through a GitHub security advisory:

https://github.com/tithi-stack/omarchy-taskspaces/security/advisories/new

Go to **Security → Advisories → New draft advisory**. No response time is promised.

Problems in Omarchy, Hyprland, or the other tools Taskspaces calls belong with those projects.
