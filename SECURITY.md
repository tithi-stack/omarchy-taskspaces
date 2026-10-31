# Security Policy

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## What taskhop does on your machine

- Runs local commands only: `hyprctl` (move, rename, focus, and close windows), `jq`, `python3`, and Omarchy's menu and notification commands.
- Makes no network calls and does not use `sudo`.
- Writes only to its runtime directory, `$XDG_RUNTIME_DIR/taskhop`. It does not edit your Hyprland config. You add the bindings yourself.
- `taskhop finish` can close windows. An app may ask you to save, and taskhop does not answer that prompt.
- The bar widget only reads the workspace name from Hyprland.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through a GitHub security advisory:

https://github.com/tithi-stack/taskhop/security/advisories/new

Go to **Security → Advisories → New draft advisory**. No response time is promised.

Problems in Omarchy, Hyprland, or the other tools taskhop calls belong with those projects.
