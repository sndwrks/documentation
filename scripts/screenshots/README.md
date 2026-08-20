# Documentation screenshot harness

Drives a live sndwrks Local instance with Playwright and regenerates every
screenshot in `src/assets/screenshots/`.

## Setup

```sh
uv sync --group screenshots
uv run --group screenshots playwright install firefox
```

## Running

```sh
# what the show file needs to contain
uv run --group screenshots scripts/screenshots/capture.py --checklist

# what would be captured, without capturing
uv run --group screenshots scripts/screenshots/capture.py --list

# capture everything
uv run --group screenshots scripts/screenshots/capture.py

# capture one page's worth
uv run --group screenshots scripts/screenshots/capture.py --only settings_
uv run --group screenshots scripts/screenshots/capture.py --only macros_ --only router_
```

## Adoption shots

The device adoption screenshots live in their own manifest
(`manifest_adoption.py`, prefix `adoption_`) and have their own runner:

```sh
uv run --group screenshots scripts/screenshots/capture_adoption.py --checklist
uv run --group screenshots scripts/screenshots/capture_adoption.py
```

They are separate because they cannot be captured on demand.
`PendingAdoptionsSection` renders `null` unless a device is actually sitting in
the adoption queue, and approving one empties the queue again — so the state has
to be staged by hand right before the run, and a full `capture.py` run would
otherwise fail two shots every time.

A default run captures `docs` only. Use `--manifest all` for everything.

The first run opens a headed browser and pauses:

1. Sign in as a **full-permission admin**. Route guards bounce users without
   view permission back to the overview, so a limited account silently loses
   half the shots.
2. Load your screenshot show file.
3. Press Enter.

The session is saved to `.auth/state.json` (gitignored) and reused. Later runs
skip the pause entirely. Force the pause again with `--fresh` — do that whenever
you load a different show file, since the harness has no way to tell what data
is loaded.

Once a session exists you can run `--headless`.

The session is stored per run, not per engine, so switching `--browser` after
signing in reuses the same cookie jar. If the app rejects it, re-run with
`--fresh`.

## Options

| Flag | |
|---|---|
| `--manifest NAME` | Which shot set to capture: `docs` (default), `adoption`, or `all`. Repeatable |
| `--base-url URL` | App URL. Also `SNDWRKS_BASE_URL`. Default `https://local.sndwrks.test:4080` |
| `--only PATTERN` | Capture only matching shots. Repeatable. Substring match, or a glob if it contains `*` |
| `--skip PATTERN` | Skip matching shots. Repeatable |
| `--fresh` | Ignore the saved session and pause for sign-in |
| `--headless` | Run headless (needs a saved session) |
| `--browser NAME` | `firefox` (default), `chromium` or `webkit`. Also `SNDWRKS_BROWSER` |
| `--include-destructive` | Include shots that change server state, e.g. starting a network scan |
| `--no-sidebar-pin` | Leave the nav sidebar collapsed |
| `--no-freeze` | Leave CSS animations and transitions enabled |
| `--keep-toasts` | Leave notification toasts on screen instead of waiting them out |
| `--list` / `--checklist` | Print and exit |

## Output

PNGs land in `src/assets/screenshots/` at 1600×1000 with a device scale factor
of 2, so 3200×2000 actual pixels. `starlightImageZoom()` is enabled on the docs
site, so the extra resolution gets used.

The script **never edits `.mdx` files**. At the end it prints the exact markdown
line to paste for any screenshot that no page references yet, plus a list of
stale assets that neither the manifest nor any page owns.

Failures are isolated per shot — a broken selector never kills the run. The
failing step is named in the report and the page state is dumped to
`.debug/<name>.png` and `.debug/<name>.html`.

## Editing the manifest

`manifest.py` is the file you edit, with `manifest_adoption.py` alongside it
for the adoption shots. `capture.py` just executes them.

```python
Shot(
    name="settings_backup-restore",              # -> settings_backup-restore.png
    doc=SOFTWARE + "settings.mdx",               # which page it belongs to
    alt="The backup and restore settings panel", # alt text in the printed markdown
    goto="/settings/backupRestore",
    ready=[heading("Backup & Restore")],         # wait for these before doing anything
    steps=[],                                    # then do these
    clip=None,                                   # CSS selector -> element shot
    needs=None,                                  # what the show file must contain
)
```

The step vocabulary lives in `steps.py`: `click`, `click_if`, `click_sel`,
`click_text`, `click_node`, `row_menu`, `select`, `check`, `fill`, `press`,
`hover`, `scroll_to`, and the waits `text`, `gone`, `heading`, `button`, `link`,
`textbox`, `dialog`, `selector`, `sleep`.

At the top of `manifest.py` is a block of show-file bindings — `DEMO_MACRO`,
`OSC_TRIGGER`, `DEMO_CHANNEL` and friends. Rename those to match whatever you
actually build rather than editing individual shots.

## Notes on the app

Things that shape how this harness works, all verified against
`../sndwrks-local/local-frontend`:

- **Every tab and settings panel is a real URL path** (`/router/sacn`,
  `/settings/backupRestore`). The harness navigates rather than clicking tabs.
  Two settings panel ids are camelCase: `hazeWatch`, `backupRestore`.
- **The sidebar is collapsed by default** (`Body.tsx`). Labels sit at
  `opacity: 0` — visible to Playwright, invisible in a screenshot — so the
  harness expands it first. The pin toggle has no accessible name and is
  located structurally, which makes it the most fragile thing here.
- **Tab links have `text-transform: lowercase`** and Playwright honours that
  when computing accessible names. All name matching in `steps.py` is
  case-insensitive for this reason.
- **Auth is an httpOnly cookie** (`sndwrks_session`), no localStorage token, no
  CSRF. Playwright's `storage_state` handles it cleanly.
- **There is no login route.** `AuthGate` wraps the app outside the router, so
  the login screen renders at whatever URL is in the bar.
- **Every page load raises a toast.** `EStopSocketHandler` announces the
  e-stop status on socket connect, so "The e-stop is currently not engaged."
  lands in the header on every shot. The harness dismisses it and waits for
  `[data-testid='header-notifications']` to detach — the component renders
  null when nothing is queued — both after the app shell mounts and again
  just before capture, since a step's own click can raise one. Auto-close is
  5s if the dismiss button is unreachable. Pass `--keep-toasts` to disable.
- **Dark theme only**, hardcoded in `index.html`. Nothing to toggle.
- **Never wait on `networkidle`** — socket.io holds a connection open, so it
  never fires. Use explicit readiness gates.

## Calibrating

Entries marked `# CALIBRATE` in `manifest.py` use a selector inferred from the
docs prose rather than read off the app's route table. Expect to fix those on
the first run.

Work page by page:

1. `--only settings_` first. Those are pure navigation with no interaction, so
   they prove the session, the sidebar pin and the capture path all work.
2. Then `--only devices_`, `--only macros_`, and so on.
3. When a shot fails, open `.debug/<name>.html`, find the real selector, fix the
   line in `manifest.py`, re-run just that shot.

## Not covered

The browser's certificate-untrusted warning described in `quick-setup.mdx` is
browser chrome, not page content, and `page.screenshot()` cannot reach it. That
one stays a manual capture.
