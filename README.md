# taskhop

Turn the window you're in into a task: one key to start, one key to finish.

**Status: alpha (0.1.0).** Built for Omarchy Quattro (4.0.0.alpha). See [Status](#status).

<!-- Preview: add a screenshot or short GIF here once one exists. -->

## What it does

- **Send:** `SUPER + N` moves the focused window to a named task workspace. The name is suggested from the window title.
- **Send silently:** `SUPER + ALT + N` does the same, but you stay on your current workspace.
- **Finish:** `SUPER + D` closes the task's windows or moves them back, after asking you first. The bar widget shows the task name.

The keys are suggestions. You choose them in [Bindings](#bindings).

## How it differs

Each part of this idea exists in other projects. taskhop adds the combination: one key sends a window to a task named from its title, a silent variant, and a finish that closes or returns the windows. Numbered workspaces keep their names and bindings, except that a task takes one number (see [Workspace numbers](docs/how-it-works.md#workspace-numbers)).

- **[jsimonrichard/hypr-taskspace](https://github.com/jsimonrichard/hypr-taskspace)** is a heavier task manager. Each task gets its own named workspaces. It can use git worktrees for linked repos, runs a systemd user daemon (`tskd`), and opens a control overlay on `SUPER + Tab`. Choose it if you want that model.
- **[tornikegomareli/omarchy-spaces](https://github.com/tornikegomareli/omarchy-spaces)** is a different tool: a bar workspace switcher that shows the apps open on each workspace. Its README describes switching and previews, not sending windows to tasks.

taskhop has no daemon and no overlay. It is one helper script and one bar widget. Both project descriptions were checked on 2026-10-30.

## Requirements

| Requirement | Used for |
|---|---|
| Omarchy Quattro (4.0.0.alpha) | Plugin system and Lua bindings |
| Hyprland, with `hyprctl` on `PATH` | Moving, renaming, focusing, and closing windows |
| `jq`, `python3`, `flock`, `bash`, GNU coreutils | Script logic, name rules, and a lock so one action runs at a time |
| `omarchy-menu-select`, `omarchy-menu-input`, `omarchy-notification-send` | Menus, the name prompt, and notifications. These ship with Omarchy. |

Check your Omarchy version with `cat /usr/share/omarchy/version`.

The helper also needs the `XDG_RUNTIME_DIR` variable set. See [Troubleshooting](#troubleshooting).

## Install

1. Add the plugin. Omarchy shows a warning and asks you to confirm before it clones.
   ```bash
   omarchy plugin add https://github.com/tithi-stack/taskhop
   ```
2. Enable it. If you answered yes to "Enable now?" in step 1, skip this step.
   ```bash
   omarchy plugin enable tithi-stack.taskhop
   ```
3. Optional: place the widget in a bar section. It starts in its default section, which is the center unless its manifest sets another. To move it:
   ```bash
   omarchy bar move tithi-stack.taskhop --section center
   ```
4. Paste the bindings from [Bindings](#bindings) into `~/.config/hypr/bindings.lua`. taskhop never edits this file.
5. Reload Hyprland, then check for config errors. Fix any errors before you test.
   ```bash
   hyprctl reload && hyprctl configerrors
   ```
6. Optional: put the helper on your `PATH`, if `~/.local/bin` is on it.
   ```bash
   ln -s ~/.config/omarchy/plugins/tithi-stack.taskhop/bin/taskhop ~/.local/bin/taskhop
   ```

Updates: `omarchy plugin update tithi-stack.taskhop`. The bindings point at the helper inside the plugin folder, so you do not change them after an update.

## Bindings

Paste these into `~/.config/hypr/bindings.lua`:

```lua
-- taskhop: send the focused window to a task, or finish the task
local taskhop_bin = os.getenv("HOME") .. "/.config/omarchy/plugins/tithi-stack.taskhop/bin/taskhop"
o.bind("SUPER + N", "Send window to task", taskhop_bin .. " send")
o.bind("SUPER + ALT + N", "Send window to task (stay here)", taskhop_bin .. " send --silent")
o.bind("SUPER + D", "Finish task", taskhop_bin .. " finish")
```

| Keys | Action | Command |
|---|---|---|
| `SUPER + N` | Send the focused window to a task, then follow it | `taskhop send` |
| `SUPER + ALT + N` | Send the focused window to a task, and stay here | `taskhop send --silent` |
| `SUPER + D` | Finish the current task | `taskhop finish` |

`taskhop --help` prints usage. `taskhop --version` prints `0.1.0`.

### Conflict check

- The default bindings in `/usr/share/omarchy/default/hypr/bindings/*.lua` on Omarchy 4.0.0.alpha do **not** use `SUPER + N`, `SUPER + ALT + N`, or `SUPER + D`. I checked by reading those files. Omarchy Quattro was not checked.
- To check your own setup after you paste the bindings:
  ```bash
  hyprctl -j binds | jq -r '.[] | select(.key == "N" or .key == "D") | "\(.modmask) \(.key) \(.dispatcher)"'
  ```
  Modmask `64` means `SUPER`, and `72` means `SUPER + ALT`. If a line for the same key and modmask belongs to another bind, that key is already taken.
- To rebind a taken key, call `hl.unbind("SUPER + N")` before the matching `o.bind(...)` line, and note what the key did before.

## Usage

1. Focus the window you want to move. For example, a VS Code window titled `Fix login bug - Visual Studio Code`.
2. Press `SUPER + N`. A menu opens.
3. Choose **New task: Fix login bug**, or **New task, type a name…** to enter your own. Press Enter.
4. The window moves to a new workspace named after the task, and you follow it. A notification says `Task "Fix login bug" → workspace N`.
5. Work in the task. The bar shows `◆ Fix login bug`.
6. Press `SUPER + D` to finish. If the task still has windows, a menu offers **Close N windows and finish**, **Move windows to ws N and finish** (or **Keep windows here and finish** for a task made from a numbered workspace), or **Cancel**.
7. Choose one. A window that stays open, for example because an app asks you to save, keeps the task. taskhop stops waiting after 30 seconds and notifies you of what is still open.

To send without following, press `SUPER + ALT + N` in step 2. The full menu rows and naming rules are in [How taskhop works](docs/how-it-works.md).

## Uninstall

1. Delete the `taskhop_bin` line and the three `o.bind` lines from `~/.config/hypr/bindings.lua`. Then run `hyprctl reload`.
2. If you made the optional symlink in step 6, remove it: `rm ~/.local/bin/taskhop`.
3. Remove the plugin. This disables it, then deletes its folder:
   ```bash
   omarchy plugin remove tithi-stack.taskhop
   ```
4. Optional: delete leftover task records. They are runtime files, so logging out also clears them.
   ```bash
   rm -rf "${XDG_RUNTIME_DIR:?}/taskhop"
   ```

## Troubleshooting

- **The key does nothing.** Cause: another taskhop action holds the lock, and the helper exits silently when it cannot get it. Or the bind did not load. Fix: wait a second and press again. If it still does nothing, run `hyprctl configerrors`.
- **Notification: "No window focused".** Cause: no window had focus when you pressed `SUPER + N`. Fix: focus a window and press it again.
- **Notification: "This workspace isn't a task".** Cause: `SUPER + D` ran on a plain workspace. Fix: switch to the task workspace, then press `SUPER + D`.
- **An error appears in no notification.** Cause: helper errors, such as a failed `hyprctl` call, go to stderr, and a keybinding does not show stderr. Fix: run the same command from a terminal to see the message.
- **`XDG_RUNTIME_DIR is required`.** Cause: the variable is not set in that shell. Fix: run the command from your desktop session.

## FAQ

- **Does it change my Hyprland config?** No. You paste the bindings yourself. The plugin ships a helper script and a bar widget.
- **Does it use the network or sudo?** No. It runs only local commands. See [SECURITY.md](SECURITY.md).
- **Can I keep using numbered workspaces?** Yes. A task takes the lowest unused number while it exists. See [Workspace numbers](docs/how-it-works.md#workspace-numbers).
- **Does it work with a legacy `.conf` Hyprland config?** Unverified. Only the Lua form is documented here. Do not translate it yourself until it is verified.
- **Is it in a plugin marketplace?** Not yet.

## Status

- Version 0.1.0, alpha. Target: Omarchy Quattro (4.0.0.alpha).
- Automated tests use mock `hyprctl` and menu commands. Quattro has not been tested yet.
- Legacy `.conf` support: unverified.
- Limits: a task takes a workspace number. Finish can close windows, and taskhop does not answer their save prompts.

## More

- [How taskhop works](docs/how-it-works.md): menus, naming rules, finish behavior, and state files
- [CONTRIBUTING.md](CONTRIBUTING.md): tests and how to propose changes
- [SECURITY.md](SECURITY.md): what the plugin runs, and how to report a vulnerability
- [CHANGELOG.md](CHANGELOG.md): release history

## License

MIT. See [LICENSE](LICENSE).
