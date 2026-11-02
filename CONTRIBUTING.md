# Contributing to Taskspaces

Thanks for helping. Taskspaces is one helper script and one bar widget, so small, focused changes are easiest to review.

## Before you start

- For anything bigger than a typo or a small fix, open an issue first.
- The command-line surface is part of the contract, because keybindings depend on it. `send`, `send --silent`, `finish`, `go`, `setup`, `browser`, `--help`, and `--version` need an issue before you change them.

## Set up

```bash
git clone https://github.com/tithi-stack/omarchy-taskspaces.git
cd omarchy-taskspaces
```

Run the tests from the repository root:

```bash
python3 -m unittest discover -s tests
```

The tests use only the Python standard library. They replace `hyprctl` and the Omarchy menu commands with mock executables in temporary directories, so they do not touch your desktop.

To check the plugin folder against Omarchy's manifest rules:

```bash
omarchy plugin validate .
```

## Continuous integration

GitHub Actions runs the tests, ShellCheck on `bin/taskspaces`, and a dry-run check on every push and pull request. The workflow is in `.github/workflows/ci.yml`.

## Making a change

1. Fork the repository, then create a branch from `main`.
2. Write a failing test for the behavior you want, then make it pass.
3. Keep one logical change per commit.
4. If the change is visible to users, add a line under `## [0.1.0] - Unreleased` in `CHANGELOG.md`.
5. Open a pull request. Describe what changed, why, and how you tested it. The pull request template has a checklist.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>
```

- Types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `perf`, `style`.
- The summary is imperative, lowercase, has no period, and is at most 72 characters.

## Versions

Keep the version in `manifest.json` and the output of `taskspaces --version` the same. Releases follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Keep personal data out

Do not commit personal paths, user names, email addresses, account identifiers, or machine-specific config. This applies to code, tests, fixtures, and docs. Window titles can contain private text, so use made-up titles in tests and in bug reports.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
