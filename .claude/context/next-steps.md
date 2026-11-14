# Next steps

[← Project Context](../PROJECT_CONTEXT.md)

1. **The first catalog bump, `/release` step 12, for 26.11.0.** The first catalog pin is `fde0a1f` (#77's commit, labelled 26.10.6), not a release commit — use it as the old end of the compare link. 26.11.0 raises the floor to 26.11.2: the dev disclosure's version and checksum filename change to `v26.11.2` and `scripts/mariadb-shell-v26.11.2.SHA256SUMS` (twice each).
2. **Turn on "Enforce HTTPS" on the fork's Pages settings** — until then `mariadb.github.io/ai-plugins/` 301s to `http://` and plain-http visits aren't upgraded.
3. **Hero code cut-off on phones — finish or decide not to.** The longest sample line is ~391px of monospace against a ~278px panel at 390px, so no box-model change closes it. Options: (a) wrap long lines below the threshold (`white-space: pre-wrap` + a hanging indent) — the only one that shows everything at 320px; (b) shorten the sample in `docs/index.html`; (c) keep the horizontal scroll, which the `…` marker announces.
4. (Optional, a11y) **Make scrollable code blocks keyboard-reachable** — `tabindex="0"` + an accessible name, on every code block of the site.
5. **Move Hermes' `INSTALLER_COMMIT` to a mariadb-shell commit whose installers serialize concurrent installs** (mariadb-shell PR #123: install.sh lock folder, install.ps1 mutex), in both Hermes `.sh` and `.cmd` — the move must reach the catalog entry (`/release` step 12). Check also that the x86 Windows package of the current shell runs `mcp start-server` (pywin32, see gotchas).
6. **Once a stable (non-prerelease) `mariadb-shell` release exists**, drop the prerelease guidance from the main README and the plugin READMEs; the launcher's prerelease fallback stays useful.
7. **Reference docs**: generate the MCP Tool Reference from the plugin's docstrings, document `rest.*`/`restd.*` once a shell release ships the renamed groups, then port to mariadb-docs. Ordered list in [reference docs](docs-ref.md#next-steps).
8. **SE video**: decide the pause after "MariaDB" (166 ms now; a 60 ms A/B clip is in the gitignored work dir). If the user prefers 60 ms, generalize `tts.py`'s `{pause:S}` into a marker that resizes the natural gap without speaking a comma. Before it goes beyond SE: the user watches it in full with sound and Marketing signs off on logo/colours; if it should be downloadable, attach the mp4 to a GitHub release (or Git LFS) rather than committing it (~52 MB).
9. (Optional) Propagate the REST/MSM e2e steps to the opencode suite (codex has them; pi can reach the server through codemode).
10. (Optional) Teach CI to use `run_tests.py` — needs a `mariadb-shell` on the runner.
11. (Optional) Verify the Hermes docs' Windows path (`.cmd` launcher) on a machine with enough disk for Hermes (~1.4 GB); it is untested.
