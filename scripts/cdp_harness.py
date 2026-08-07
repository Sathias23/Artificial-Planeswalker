"""A committed CDP harness: drive a real browser against a real companion, and measure.

**Why this exists.** Every eye-check and every performance number in Epic C4 was produced by an
ad-hoc CDP script written into a scratchpad and thrown away. That was sanctioned at the time
(c4-12 Task 4), and it left two ledgered residues: the render-budget numbers in
``ui/src/App.tsx``'s two effect comments are **irreproducible from the repo** while those comments
carry a "DO NOT REORDER WITHOUT RE-MEASURING" instruction, and the probe/eye-check harness was
**rebuilt from scratch by every story** — and lied five times across the epic, each time caught
only by its own negative controls. Promoted at the Epic C4 retrospective (2026-08-07).

This module is the house pattern written down rather than a new one. c4-12's own Q9 specifies it:
*"ad-hoc CDP in Python (websockets + httpx), Chrome --headless=new, fresh profile, against the
committed SPA served by the running backend."* The only change is that it is now committed, so the
next reader re-runs a measurement instead of re-deriving a method.

**It is a developer tool, not shipped code.** It lives in ``scripts/`` beside the other operator
utilities, imports nothing from ``src/companion``, and is never packaged into ``plugin/``.

Usage::

    uv run python -m scripts.cdp_harness budget --data-dir <dir>   # cold-open budget (NFR-05)
    uv run python -m scripts.cdp_harness panels                    # state panels (Block I)
    uv run python -m scripts.cdp_harness shot --url http://127.0.0.1:8765 --out x.png

Every subcommand runs the companion against an **isolated data directory** unless ``--data-dir``
says otherwise, so a measurement can never write to the operator's real one.

**The three traps this harness is built to refuse**, all of them recorded failures from C4 rather
than hypotheticals:

1. **A run that collected no assertions reads as a pass.** Every C4 probe harness that lied did so
   by producing zero results and being scored anyway. :meth:`Browser.js` raises on a JS exception,
   and the budget command refuses a run whose surfaces did not all arrive.
2. **A lowercase drive letter in ``cwd`` breaks vitest's project resolution** (ledgered) and a
   forward-slash ``cwd`` broke it twice. Paths here are resolved with :meth:`Path.resolve`.
3. **``subprocess.run([...], shell=True)`` on Windows passes only the first list element**, which
   is how a c4-10 probe run reported every probe caught while nothing ran, and how this harness's
   own first draft stranded a backend holding ``cards.db``. Nothing here uses ``shell=True``.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

# The six surfaces AC 3 names, and the hooks that prove each one is in the DOM. Five derive from
# `boards` and paint on the deck-detail commit; the sixth (format check) is a separate request and
# is the one the effect ordering moves. Selectors are shipped class names, not test ids.
SURFACES: dict[str, str] = {
    "header": "header h1",
    "grid": ".card-grid",
    "curve": ".mana-curve",
    "colour": ".colour-distribution",
    "deck-list": ".deck-list",
    "format-check": ".format-check-rows",
}


def find_chrome() -> Path:
    """Locate a Chrome binary, or explain what to pass instead."""
    override = os.getenv("CHROME_BINARY")
    if override:
        return Path(override)
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "No Chrome found. Set CHROME_BINARY to the executable, e.g.\n"
        r"  set CHROME_BINARY=C:\Program Files\Google\Chrome\Application\chrome.exe"
    )


def free_port() -> int:
    """Ask the OS for a port nothing is using."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


class Browser:
    """A real headless Chrome on a fresh profile, driven over the DevTools protocol."""

    def __init__(self, headless: bool = True, width: int = 1440, height: int = 1000) -> None:
        import websockets.sync.client as wsc

        self.port = free_port()
        self.profile = Path(tempfile.mkdtemp(prefix="cdp-harness-"))
        args = [
            str(find_chrome()),
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-extensions",
        ]
        if headless:
            args.append("--headless=new")
        args.append("about:blank")
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._await_debugger()
        targets = httpx.get(f"http://127.0.0.1:{self.port}/json/list", timeout=10).json()
        page = next(t for t in targets if t["type"] == "page")
        self.ws = wsc.connect(page["webSocketDebuggerUrl"], max_size=100 * 1024 * 1024)
        self._next_id = 0
        self.events: list[dict[str, Any]] = []
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=False,
        )

    def _await_debugger(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                httpx.get(f"http://127.0.0.1:{self.port}/json/version", timeout=1.0)
                return
            except httpx.HTTPError:
                time.sleep(0.2)
        raise RuntimeError("Chrome never opened its debugging port")

    def send(self, method: str, **params: Any) -> dict[str, Any]:
        """Issue one CDP command and return its result, buffering any events that arrive first."""
        self._next_id += 1
        message_id = self._next_id
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                result: dict[str, Any] = message.get("result", {})
                return result
            # Anything that is not our reply is an event and is KEPT. Dropping events is how a
            # request-counting instrument silently measures nothing.
            if "method" in message:
                self.events.append(message)

    def pump(self, seconds: float) -> None:
        """Collect events for a while without issuing a command."""
        end = time.time() + seconds
        while True:
            remaining = end - time.time()
            if remaining <= 0:
                return
            try:
                message = json.loads(self.ws.recv(timeout=remaining))
            except Exception:
                return
            if "method" in message:
                self.events.append(message)

    def on_new_document(self, script: str) -> None:
        """Run *script* at document-start on every navigation.

        Load-time is too late for anything that observes arrival: an observer added at load misses
        every surface that got there first. c4-12's Q7 ruling names document-start for exactly this.
        """
        self.send("Page.addScriptToEvaluateOnNewDocument", source=script)

    def navigate(self, url: str, settle: float = 2.0) -> None:
        self.send("Page.navigate", url=url)
        time.sleep(settle)

    def reload(self, ignore_cache: bool = True, settle: float = 2.0) -> None:
        self.send("Page.reload", ignoreCache=ignore_cache)
        time.sleep(settle)

    def js(self, expression: str, await_promise: bool = True) -> Any:
        """Evaluate *expression* in the page and return its value, raising on a JS exception."""
        result = self.send(
            "Runtime.evaluate",
            expression=expression,
            returnByValue=True,
            awaitPromise=await_promise,
        )
        if "exceptionDetails" in result:
            raise RuntimeError(f"page threw: {result['exceptionDetails'].get('text')}")
        return result["result"].get("value")

    def block(self, patterns: list[str]) -> None:
        """Fail matching requests at the transport layer, so ``fetch`` rejects with no response."""
        self.send("Network.enable")
        self.send("Network.setBlockedURLs", urls=patterns)

    def unblock(self) -> None:
        self.send("Network.setBlockedURLs", urls=[])

    def screenshot(self, path: Path) -> None:
        data = self.send("Page.captureScreenshot", format="png")["data"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def __enter__(self) -> Browser:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class Companion:
    """The companion backend as a child process, against a data directory you choose."""

    def __init__(self, data_dir: Path, port: int | None = None) -> None:
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.port = port or free_port()
        self.proc: subprocess.Popen[bytes] | None = None
        self.log_path = self.data_dir / "companion.log"
        self._log: Any = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, wait: bool = True) -> None:
        env = dict(os.environ)
        env["PLANESWALKER_DATA_DIR"] = str(self.data_dir)
        self._log = self.log_path.open("ab")
        self.proc = subprocess.Popen(
            ["uv", "run", "artificial-planeswalker", "companion", "--port", str(self.port)],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )
        if wait:
            self.await_up()

    def await_up(self, timeout: float = 120.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                httpx.get(f"{self.url}/health", timeout=1.0)
                return
            except httpx.HTTPError:
                time.sleep(0.4)
        raise RuntimeError(f"companion did not start; see {self.log_path}")

    def stop(self) -> None:
        """Kill the whole child tree, then wait for the port to actually free.

        The tree matters: ``uv run`` spawns the real server as a grandchild, so terminating the
        immediate child leaves a process holding the port AND ``cards.db`` open -- which is what
        makes the *next* run fail to clean its own data directory.
        """
        if self.proc is None:
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        if self._log is not None:
            self._log.close()
            self._log = None

    def await_down(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                httpx.get(f"{self.url}/health", timeout=1.0)
                time.sleep(0.3)
            except httpx.HTTPError:
                return
        raise RuntimeError("companion still answering after stop()")

    def __enter__(self) -> Companion:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


# ---------------------------------------------------------------------------- the render budget

_OBSERVER = """
(() => {
  const SEL = __SELECTORS__;
  window.__surfaces = {};
  window.__observerError = null;
  window.__t0 = performance.timeOrigin;
  const seen = (name) => {
    if (window.__surfaces[name] === undefined) window.__surfaces[name] = performance.now();
  };
  const sweep = () => {
    for (const [name, sel] of Object.entries(SEL)) {
      if (document.querySelector(sel)) seen(name);
    }
  };
  try {
    // OBSERVE `document`, NOT `document.documentElement`. This script runs at document-start,
    // where documentElement is still null -- `.observe(null)` throws, the IIFE aborts after
    // setting __surfaces = {}, and every run then reports "no surfaces arrived" while the page
    // renders perfectly. Measured: that is exactly what the first version of this harness did.
    new MutationObserver(sweep).observe(document, { childList: true, subtree: true });
    sweep();
  } catch (e) {
    // Never fail silently. A measurement instrument that dies at install time and leaves an
    // empty result is indistinguishable from a page that rendered nothing.
    window.__observerError = String(e);
  }
})()
"""


def measure_budget(url: str, browser: Browser, settle: float = 25.0) -> dict[str, Any]:
    """One cold-open run: when did each of the six named surfaces enter the DOM?

    The clock is ``performance.timeOrigin`` read **in the page**, so there is no cross-process
    clock to align, and the stop is the LAST of the six -- c4-12's Q7 ruling, unchanged.
    """
    browser.on_new_document(_OBSERVER.replace("__SELECTORS__", json.dumps(SURFACES)))
    browser.send("Network.enable")
    browser.navigate(url, settle=settle)
    surfaces: dict[str, float] = browser.js("window.__surfaces") or {}
    observer_error = browser.js("window.__observerError")
    missing = sorted(set(SURFACES) - set(surfaces))
    resources = browser.js(
        "performance.getEntriesByType('resource')"
        ".map(e => ({name: e.name, start: e.startTime, dur: e.duration}))"
    )
    fc = [r for r in resources if "format-check" in r["name"]]
    cards = [r for r in resources if "/api/cards/" in r["name"]]
    before_fc = len([r for r in resources if r["start"] < fc[0]["start"]]) if fc else None
    return {
        "surfaces": surfaces,
        "missing": missing,
        "observer_error": observer_error,
        "layout_ms": max(surfaces.values()) if surfaces and not missing else None,
        "requests_total": len(resources),
        "card_reads": len(cards),
        "format_check_queue_position": before_fc,
        "format_check_start_ms": fc[0]["start"] if fc else None,
    }


def cmd_budget(args: argparse.Namespace) -> int:
    """Re-measure the cold-open render budget that ``ui/src/App.tsx``'s effect comments cite."""
    data_dir = Path(args.data_dir).resolve() if args.data_dir else None
    if data_dir is None:
        raise SystemExit(
            "budget needs --data-dir pointing at a data directory holding a REAL cards.db and an\n"
            "active deck; it measures a loaded deck view. Copy your data dir, do not share it."
        )
    runs: list[dict[str, Any]] = []
    companion = Companion(data_dir, args.port)
    companion.start()
    try:
        print(f"companion on {companion.url}, data dir {data_dir}")
        # The active deck lives in BACKEND MEMORY (c3-4: the route takes no session), so a freshly
        # started companion has none and the deck view would never paint. Set it here or the whole
        # measurement silently becomes "how fast does an empty view render".
        token = json.loads((data_dir / "companion.json").read_text(encoding="utf-8"))["token"]
        response = httpx.put(
            f"{companion.url}/api/active-deck",
            json={"deck_id": args.deck_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if response.status_code != 200:
            raise SystemExit(
                f"could not set the active deck: {response.status_code} {response.text}"
            )
        print(f"active deck set to {args.deck_id}")
        for index in range(args.runs):
            # A FRESH PROFILE PER RUN or the arm is not the arm: reusing one profile turns a
            # cold-open measurement into a warm-HTTP-cache measurement after run 1.
            with Browser(headless=not args.headed) as browser:
                result = measure_budget(companion.url, browser, settle=args.settle)
            runs.append(result)
            if result["missing"]:
                why = result.get("observer_error") or "the page did not render them"
                print(
                    f"  run {index + 1}: INVALID -- surfaces never arrived: "
                    f"{result['missing']} ({why})"
                )
            else:
                print(
                    f"  run {index + 1}: layout {result['layout_ms']:.0f} ms  "
                    f"format-check at queue position {result['format_check_queue_position']}  "
                    f"({result['card_reads']} card reads, {result['requests_total']} requests)"
                )
    finally:
        companion.stop()

    good = [r for r in runs if not r["missing"]]
    if not good:
        # A run that measured nothing must not be reported as a number. Every harness that lied in
        # Epic C4 lied by scoring an empty run.
        print("\nNO VALID RUNS -- refusing to report a number.", file=sys.stderr)
        return 1
    times = [r["layout_ms"] for r in good]
    print(
        f"\nlayout time over {len(good)}/{len(runs)} valid runs: "
        f"min {min(times):.0f} / median {statistics.median(times):.0f} / max {max(times):.0f} ms"
        f"   (NFR-05 budget: 1000 ms)"
    )
    positions = {r["format_check_queue_position"] for r in good}
    print(f"format-check queue position(s): {sorted(p for p in positions if p is not None)}")
    if args.json:
        Path(args.json).write_text(json.dumps(runs, indent=2), encoding="utf-8")
        print(f"raw runs -> {args.json}")
    return 0 if max(times) < 1000 else 2


# ---------------------------------------------------------------------------- the state panels

_PANEL_JS = """
(() => {
  const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
  const panel = document.querySelector('.state-panel');
  return {
    panelPresent: !!panel,
    panelText: panel ? clean(panel.textContent) : null,
    headings: [...document.querySelectorAll('h1,h2')].map(e => clean(e.textContent)),
    liveRegions: document.querySelectorAll('[aria-live],[role=status],[role=alert]').length,
    storyKeys: [...new Set((document.body.innerText.match(/\\bc\\d+-\\d+\\b/g) || []))].sort(),
  };
})()
"""


def cmd_panels(args: argparse.Namespace) -> int:
    """Render the system-state panels a unit test cannot see (manual-checklist Block I).

    Two of the four states are produced by REAL backend conditions rather than stubs: no
    ``cards.db`` gives ``503 database_not_initialized``, and a ``cards.db`` that exists but is not
    a SQLite file gives a ``DatabaseError`` and therefore ``503 database_unavailable``. That the
    same status yields two different panels is the point of the check.
    """
    data_dir = (
        Path(args.data_dir).resolve()
        if args.data_dir
        else Path(tempfile.mkdtemp(prefix="cdp-panels-"))
    )
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in data_dir.glob("cards.db*"):
        stale.unlink()

    companion = Companion(data_dir, args.port)
    companion.start()
    try:
        with Browser(headless=not args.headed) as browser:
            browser.send("Network.enable")
            print(f"data dir {data_dir}")

            browser.navigate(companion.url, settle=4.0)
            info = browser.js(_PANEL_JS)
            browser.screenshot(out_dir / "database-not-initialized.png")
            print(f"  no cards.db          -> {info['headings'][1:2]}")
            print(f"     story keys on screen: {info['storyKeys']}")

            companion.stop()
            companion.await_down()
            (data_dir / "cards.db").write_bytes(b"not a sqlite database")
            companion.start()
            browser.reload(settle=4.0)
            info = browser.js(_PANEL_JS)
            browser.screenshot(out_dir / "database-updating.png")
            print(f"  corrupt cards.db     -> {info['headings'][1:2]}")

            print(f"  holding for the {args.stall_wait:.0f} s escalation ...")
            browser.pump(args.stall_wait)
            info = browser.js(_PANEL_JS)
            browser.screenshot(out_dir / "database-updating-stalled.png")
            print(f"  after the wait       -> {info['headings'][1:2]}")

            browser.block(["*/api/*"])
            browser.reload(settle=6.0)
            info = browser.js(_PANEL_JS)
            browser.screenshot(out_dir / "unreachable-first-load.png")
            print(f"  nothing reachable    -> {info['headings'][1:2]}")
            browser.unblock()
        print(f"\nscreenshots -> {out_dir}")
    finally:
        companion.stop()
    return 0


def cmd_shot(args: argparse.Namespace) -> int:
    """Screenshot a URL. The smallest useful thing this harness does."""
    with Browser(headless=not args.headed) as browser:
        browser.navigate(args.url, settle=args.settle)
        browser.screenshot(Path(args.out).resolve())
    print(f"wrote {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdp_harness",
        description="Drive a real browser against a real companion, and measure.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    budget = sub.add_parser("budget", help="re-measure the cold-open render budget (NFR-05)")
    budget.add_argument("--data-dir", required=True, help="data dir with a real cards.db")
    budget.add_argument(
        "--deck-id", required=True, help="deck to make active (the view being measured)"
    )
    budget.add_argument("--runs", type=int, default=5, help="runs per arm (c4-12 used 5)")
    budget.add_argument("--arm", default="fresh", choices=["fresh"], help="cache arm")
    budget.add_argument("--settle", type=float, default=25.0)
    budget.add_argument("--port", type=int, default=None)
    budget.add_argument("--json", default=None, help="write raw per-run results here")
    budget.add_argument("--headed", action="store_true")
    budget.set_defaults(func=cmd_budget)

    panels = sub.add_parser("panels", help="render the system-state panels (Block I)")
    panels.add_argument("--data-dir", default=None, help="defaults to a fresh temp dir")
    panels.add_argument("--out", default="cdp-panels", help="screenshot directory")
    panels.add_argument("--stall-wait", type=float, default=70.0)
    panels.add_argument("--port", type=int, default=None)
    panels.add_argument("--headed", action="store_true")
    panels.set_defaults(func=cmd_panels)

    shot = sub.add_parser("shot", help="screenshot a URL")
    shot.add_argument("--url", required=True)
    shot.add_argument("--out", default="shot.png")
    shot.add_argument("--settle", type=float, default=3.0)
    shot.add_argument("--headed", action="store_true")
    shot.set_defaults(func=cmd_shot)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
