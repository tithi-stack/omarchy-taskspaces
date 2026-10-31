# Security Policy

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## What taskhop does on your machine

- Runs local commands only: `hyprctl` (move, rename, focus, and close windows), `jq`, `python3`, `flock`, Omarchy's menu commands, and a notification command (`omarchy-notification-send`, or `notify-send` as a fallback).
- Makes no network calls and does not use `sudo`.
- Writes only under `$XDG_RUNTIME_DIR`: task records in `$XDG_RUNTIME_DIR/taskhop/`, and a lock file, `$XDG_RUNTIME_DIR/taskhop.lock`. It does not edit your Hyprland config. You add the bindings yourself.
- `taskhop finish` can close windows. An app may ask you to save, and taskhop does not answer that prompt.
- The bar widget only reads the workspace name from Hyprland.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through a GitHub security advisory:

https://github.com/tithi-stack/taskhop/security/advisories/new

Go to **Security → Advisories → New draft advisory**. No response time is promised.

Problems in Omarchy, Hyprland, or the other tools taskhop calls belong with those projects.
