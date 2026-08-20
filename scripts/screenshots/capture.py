#!/usr/bin/env python3
"""Regenerate the documentation screenshots by driving a live sndwrks Local instance.

The first run opens a headed browser and pauses so you can sign in and load your
screenshot show file. The session is then saved and reused, so later runs go
straight to capturing.

    uv sync --group screenshots
    uv run --group screenshots playwright install firefox
    uv run --group screenshots scripts/screenshots/capture.py

See README.md in this directory.
"""

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from manifest import SHOTS  # noqa: E402
from manifest_adoption import ADOPTION_SHOTS  # noqa: E402

# Shot sets selectable with --manifest. Adoption lives apart because its shots
# need a device staged in the adoption queue right before the run — see
# manifest_adoption.py.
MANIFESTS = {
    "docs": SHOTS,
    "adoption": ADOPTION_SHOTS,
}


def _playwright():
    """Imported lazily so --list and --checklist work without the dependency."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "playwright is not installed.\n"
            "  uv sync --group screenshots\n"
            "  uv run --group screenshots playwright install firefox"
        )
    return sync_playwright

REPO_ROOT = SCRIPT_DIR.parent.parent
DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
OUTPUT_DIR = REPO_ROOT / "src" / "assets" / "screenshots"
STATE_PATH = SCRIPT_DIR / ".auth" / "state.json"
DEBUG_DIR = SCRIPT_DIR / ".debug"

DEFAULT_BASE_URL = "https://local.sndwrks.test:4080"
VIEWPORT = {"width": 1600, "height": 1000}
DEVICE_SCALE_FACTOR = 2
BROWSERS = ("firefox", "chromium", "webkit")

# The app repo's own e2e suite uses the settings nav link as its "chrome
# mounted" signal (local-frontend/tests/e2e/permissionHelpers.ts). Matched as a
# substring, not anchored — nav links wrap their label next to an icon, and any
# icon that contributes text would break an anchored match.
SETTINGS_LINK = re.compile(r"settings", re.I)

# The sidebar is collapsed to 4rem by default (Body.tsx, isSidebarPinned).
SIDEBAR_PINNED_MIN_WIDTH = 120

# HeaderNotifications renders null when the store is empty, so the wrapper
# going away is a clean "no toasts on screen" gate. Every page load raises at
# least "The e-stop is currently not engaged." — EStopSocketHandler toasts the
# status on socket connect. Toasts auto-close after 5s; clicking dismiss is
# faster and also clears anything a shot's own steps raised.
NOTIFICATION_WRAPPER = "[data-testid='header-notifications']"
NOTIFICATION_DISMISS = "button[aria-label^='dismiss notification']"
NOTIFICATION_TIMEOUT_MS = 8_000
NOTIFICATION_DISMISS_ATTEMPTS = 6

# Zero-length rather than `animation: none`, so animation-fill-mode end states
# still apply and Radix overlays do not get stuck at their entry keyframe.
FREEZE_CSS = """
*, *::before, *::after {
  animation-duration: 0s !important;
  animation-delay: 0s !important;
  transition-duration: 0s !important;
  transition-delay: 0s !important;
  caret-color: transparent !important;
}
"""


class Result:
    def __init__(self, shot, status, detail=""):
        self.shot = shot
        self.status = status
        self.detail = detail


# ── CLI ──────────────────────────────────────────────────────────────


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Regenerate documentation screenshots from a live sndwrks Local instance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SNDWRKS_BASE_URL", DEFAULT_BASE_URL),
        help=f"App URL (env SNDWRKS_BASE_URL, default {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--manifest",
        action="append",
        default=[],
        choices=sorted(MANIFESTS) + ["all"],
        metavar="NAME",
        help="Which shot set to capture: "
        + ", ".join(sorted(MANIFESTS))
        + ", or all. Repeatable. Default docs.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Only capture shots matching this name pattern. Repeatable.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Skip shots matching this name pattern. Repeatable.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore the saved session and pause for sign-in again.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless. Only works once a session has been saved.",
    )
    parser.add_argument(
        "--include-destructive",
        action="store_true",
        help="Include shots that change server state (e.g. starting a network scan).",
    )
    parser.add_argument(
        "--no-sidebar-pin",
        action="store_true",
        help="Do not expand the nav sidebar before capturing.",
    )
    parser.add_argument(
        "--no-freeze",
        action="store_true",
        help="Do not disable CSS animations and transitions before capturing.",
    )
    parser.add_argument(
        "--browser",
        choices=BROWSERS,
        default=os.environ.get("SNDWRKS_BROWSER", "firefox"),
        help="Browser engine to drive. Also SNDWRKS_BROWSER. Default firefox.",
    )
    parser.add_argument(
        "--keep-toasts",
        action="store_true",
        help="Leave notification toasts on screen instead of waiting them out.",
    )
    parser.add_argument("--list", action="store_true", help="List selected shots and exit.")
    parser.add_argument(
        "--checklist",
        action="store_true",
        help="Print what the screenshot show file needs to contain, and exit.",
    )
    return parser.parse_args(argv)


def _matches(name, pattern):
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatch(name, pattern)
    return pattern in name


def selected_manifests(args):
    names = args.manifest or ["docs"]
    if "all" in names:
        return list(MANIFESTS)
    # dedupe, keep the order the manifests are declared in
    return [name for name in MANIFESTS if name in names]


def select_shots(args):
    shots = [shot for name in selected_manifests(args) for shot in MANIFESTS[name]]
    if args.only:
        shots = [s for s in shots if any(_matches(s.name, p) for p in args.only)]
    if args.skip:
        shots = [s for s in shots if not any(_matches(s.name, p) for p in args.skip)]
    if not args.include_destructive:
        shots = [s for s in shots if not s.destructive]
    return shots


# ── Browser plumbing ─────────────────────────────────────────────────


def url_for(base_url, path):
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def launch(pw, args, headless):
    return getattr(pw, args.browser).launch(headless=headless)


def new_context(browser, storage_state=None):
    return browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=DEVICE_SCALE_FACTOR,
        ignore_https_errors=True,  # the dev stack uses a self-signed cert
        storage_state=storage_state,
    )


def _is_visible(locator):
    """count() alone is not enough — hidden overlays are still in the DOM."""
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False


def wait_app_shell(page, timeout=20_000):
    """Wait for the signed-in app shell, with a useful message on failure."""
    try:
        page.get_by_role("link", name=SETTINGS_LINK).first.wait_for(
            state="visible", timeout=timeout
        )
    except Exception:
        if _is_visible(page.get_by_text("Server disconnected")):
            raise RuntimeError(
                "the app is showing 'Server disconnected' — the backend socket is not reachable"
            )
        if _is_visible(page.get_by_text("Sign in to access this sndwrks server.")):
            raise RuntimeError("not signed in — re-run with --fresh")
        raise RuntimeError("the app shell never mounted")


def clear_notifications(page, timeout=NOTIFICATION_TIMEOUT_MS):
    """Wait until no toast is on screen, dismissing any that are.

    Cosmetic, like pin_sidebar — a failure here never fails the shot. Falls
    back to waiting out the 5s auto-close if the dismiss button is unreachable.
    """
    wrapper = page.locator(NOTIFICATION_WRAPPER)
    try:
        for _ in range(NOTIFICATION_DISMISS_ATTEMPTS):
            if wrapper.count() == 0:
                return
            buttons = wrapper.locator(NOTIFICATION_DISMISS)
            if buttons.count() == 0:
                break
            buttons.first.click(timeout=2_000)
            page.wait_for_timeout(150)
        wrapper.wait_for(state="detached", timeout=timeout)
    except Exception:
        pass


def pin_sidebar(page, warned):
    """Expand the nav sidebar so its labels are legible in the capture.

    The pin toggle is an icon-only button with no accessible name, so it is
    located structurally as the last button in the nav. Cosmetic — a failure
    here warns rather than failing the shot.
    """
    try:
        nav_link = page.get_by_role("link", name=SETTINGS_LINK).first
        nav = nav_link.locator("xpath=ancestor::nav[1]")
        if not nav.count():
            nav = nav_link.locator("xpath=ancestor::*[3]")
        nav = nav.first
        box = nav.bounding_box()
        if box and box["width"] >= SIDEBAR_PINNED_MIN_WIDTH:
            return
        nav.locator("button").last.click(timeout=3_000)
        page.wait_for_timeout(400)
        box = nav.bounding_box()
        if box and box["width"] < SIDEBAR_PINNED_MIN_WIDTH and not warned:
            warned.add("sidebar")
            print(
                "  ! could not expand the sidebar — nav labels will be invisible.\n"
                "    Fix pin_sidebar() in capture.py, or pass --no-sidebar-pin.",
                file=sys.stderr,
            )
    except Exception as exc:
        if "sidebar" not in warned:
            warned.add("sidebar")
            print(f"  ! sidebar pin failed ({_short(exc)}) — continuing", file=sys.stderr)


# ── Session ──────────────────────────────────────────────────────────


def session_is_valid(pw, args):
    if not STATE_PATH.exists():
        return False
    browser = launch(pw, args, headless=True)
    try:
        context = new_context(browser, storage_state=str(STATE_PATH))
        page = context.new_page()
        page.goto(args.base_url, wait_until="domcontentloaded", timeout=30_000)
        wait_app_shell(page, timeout=15_000)
        return True
    except Exception:
        return False
    finally:
        browser.close()


def pause_for_login(pw, args, shots):
    """Open a headed browser and block until the operator has set the app up."""
    browser = launch(pw, args, headless=False)
    try:
        context = new_context(browser)
        page = context.new_page()
        try:
            page.goto(args.base_url, wait_until="domcontentloaded", timeout=60_000)
        except Exception as exc:
            raise SystemExit(f"could not reach {args.base_url}: {_short(exc)}")

        print()
        print("=" * 72)
        print(f"  A browser is open at {args.base_url}")
        print()
        print("  1. Sign in as a full-permission admin (route guards bounce")
        print("     anyone without view permission back to the overview).")
        print("  2. Load your screenshot show file.")
        print("  3. Come back here and press Enter.")
        print()
        print_checklist(shots, indent="  ")
        print("=" * 72)
        try:
            input("  Press Enter when the app is ready... ")
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("\naborted")

        try:
            wait_app_shell(page, timeout=60_000)
        except Exception as exc:
            raise SystemExit(f"could not confirm a signed-in session: {_short(exc)}")
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(STATE_PATH))
        print(f"  session saved to {_rel(STATE_PATH)}")
    finally:
        browser.close()


def ensure_session(pw, args, shots):
    if not any(shot.context == "app" for shot in shots):
        return None  # anon-only run, nothing to authenticate
    if not args.fresh and session_is_valid(pw, args):
        print(f"reusing saved session ({_rel(STATE_PATH)})")
        return str(STATE_PATH)
    pause_for_login(pw, args, shots)
    return str(STATE_PATH)


# ── Capture ──────────────────────────────────────────────────────────


def run_shot(browser, args, shot, contexts, warned):
    context = get_context(browser, args, shot.context, contexts)
    page = context.new_page()
    stage = "setup"
    try:
        for pattern in shot.block:
            page.route(pattern, lambda route: route.abort())

        stage = f"goto {shot.goto}"
        page.goto(url_for(args.base_url, shot.goto), wait_until="domcontentloaded", timeout=30_000)

        if not args.no_freeze:
            page.add_style_tag(content=FREEZE_CSS)

        if shot.context == "app" and shot.app_ready:
            stage = "app shell"
            wait_app_shell(page)
            if not args.no_sidebar_pin:
                pin_sidebar(page, warned)
            if not args.keep_toasts:
                stage = "clear notifications"
                clear_notifications(page)

        for step in shot.ready:
            stage = f"ready [{step}]"
            step.apply(page)

        for step in shot.steps:
            stage = f"step [{step}]"
            step.apply(page)

        stage = "settle"
        # again after the steps — a click can raise its own toast, and the
        # e-stop status re-fires whenever the socket reconnects
        if shot.context == "app" and not args.keep_toasts:
            clear_notifications(page)
        try:
            page.evaluate("() => document.fonts.ready.then(() => true)")
        except Exception:
            pass
        page.wait_for_timeout(shot.settle_ms)

        stage = "capture"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        target = OUTPUT_DIR / shot.filename
        if shot.clip:
            element = page.locator(shot.clip).first
            element.wait_for(state="visible", timeout=10_000)
            element.screenshot(path=str(target))
        else:
            page.screenshot(path=str(target), full_page=shot.full_page)
        return Result(shot, "ok")
    except Exception as exc:
        dump_debug(page, shot)
        return Result(shot, "failed", f"{stage} — {_short(exc)}")
    finally:
        page.close()


def get_context(browser, args, kind, contexts):
    if kind not in contexts:
        storage = contexts["_state"] if kind == "app" else None
        contexts[kind] = new_context(browser, storage_state=storage)
    return contexts[kind]


def dump_debug(page, shot):
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DEBUG_DIR / f"{shot.name}.png"))
        (DEBUG_DIR / f"{shot.name}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


# ── Reporting ────────────────────────────────────────────────────────


def doc_file(shot):
    return DOCS_ROOT / shot.doc


def markdown_line(shot):
    rel = os.path.relpath(OUTPUT_DIR / shot.filename, start=doc_file(shot).parent)
    return f"![{shot.alt}]({rel})"


def is_referenced(shot):
    path = doc_file(shot)
    if not path.is_file():
        return False
    return shot.filename in path.read_text(encoding="utf-8")


def stale_assets():
    """PNGs in the screenshot folder that no doc references and no Shot owns."""
    referenced = set()
    for path in DOCS_ROOT.rglob("*.mdx"):
        for match in re.finditer(r"[A-Za-z0-9_.-]+\.png", path.read_text(encoding="utf-8")):
            referenced.add(match.group(0))
    # every manifest, not just the selected one — otherwise a docs-only run
    # reports the adoption PNGs as stale, and vice versa
    managed = {shot.filename for shots in MANIFESTS.values() for shot in shots}
    if not OUTPUT_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in OUTPUT_DIR.glob("*.png")
        if p.name not in managed and p.name not in referenced
    )


def print_checklist(shots, indent=""):
    needs = []
    for shot in shots:
        if shot.needs and shot.needs not in needs:
            needs.append(shot.needs)
    if not needs:
        return
    print(f"{indent}The screenshot show file needs:")
    for note in needs:
        wrapped = note.replace("\n", " ")
        print(f"{indent}  - {wrapped}")
    print()


def print_report(results):
    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status == "failed"]

    print()
    print("─" * 72)
    print(f"captured {len(ok)}/{len(results)}")

    if failed:
        print()
        print("FAILED")
        for result in failed:
            print(f"  {result.shot.name}")
            print(f"    {result.detail}")
            if result.shot.needs:
                print(f"    needs: {result.shot.needs}")
        print(f"\n  debug captures and page HTML in {_rel(DEBUG_DIR)}/")

    unreferenced = [r.shot for r in ok if not is_referenced(r.shot)]
    if unreferenced:
        print()
        print("NOT YET REFERENCED IN THE DOCS — paste these in:")
        current_doc = None
        for shot in unreferenced:
            if shot.doc != current_doc:
                current_doc = shot.doc
                print(f"\n  {shot.doc}")
            print(f"    {markdown_line(shot)}")

    stale = stale_assets()
    if stale:
        print()
        print("STALE ASSETS — not in the manifest and referenced by no page:")
        for name in stale:
            print(f"  src/assets/screenshots/{name}")

    print()
    return 1 if failed else 0


def _short(exc):
    text = str(exc).strip().splitlines()
    return text[0][:200] if text else exc.__class__.__name__


def _rel(path):
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ── Entry point ──────────────────────────────────────────────────────


def main(argv=None):
    args = parse_args(argv)
    shots = select_shots(args)

    if not shots:
        print("no shots selected")
        return 1

    if args.checklist:
        print_checklist(shots)
        return 0

    if args.list:
        for shot in shots:
            flags = []
            if shot.clip:
                flags.append("clip")
            if shot.destructive:
                flags.append("destructive")
            if shot.context != "app":
                flags.append(shot.context)
            suffix = f"  [{', '.join(flags)}]" if flags else ""
            print(f"  {shot.name:42} {shot.goto}{suffix}")
        print(f"\n{len(shots)} shots")
        return 0

    results = []
    warned = set()
    with _playwright()() as pw:
        state = ensure_session(pw, args, shots)
        browser = launch(pw, args, headless=args.headless)
        contexts = {"_state": state}
        try:
            for index, shot in enumerate(shots, start=1):
                print(f"[{index}/{len(shots)}] {shot.name} ", end="", flush=True)
                result = run_shot(browser, args, shot, contexts, warned)
                results.append(result)
                print("ok" if result.status == "ok" else f"FAILED: {result.detail}")
        finally:
            browser.close()

    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
