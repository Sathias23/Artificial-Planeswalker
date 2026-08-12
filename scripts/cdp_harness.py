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
    uv run python -m scripts.cdp_harness push --data-dir <dir>     # push-to-render budget (SC-1)
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
import uuid
from datetime import UTC, datetime
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


# ------------------------------------------------------------------------- the push budget (c6-9)

# The suggestions surfaces SC-1 calls "the view": its frame, its heading, the list, and the first
# row's two text lines. The stop is the LAST of them to enter the DOM -- `measure_budget()`'s rule,
# unchanged. Selectors are shipped class names, not test ids, so a rename that moved the view would
# be caught by a run that stamps nothing rather than by a green measurement of the wrong element.
PUSH_SURFACES: dict[str, str] = {
    "dialog": ".agent-view",
    "heading": ".agent-view-title",
    "rows": ".suggestions-view-rows",
    "first-row-name": ".suggestions-view-item:first-child .suggestion-row-name",
    "first-row-reason": ".suggestions-view-item:first-child .suggestion-row-reason",
}

_SOCKET_LIVE = ".connection-pill-dot.is-live"
"""The page's own statement that its socket is open (``ConnectionPill.tsx:129``). Pushing before
this is up measures a broadcast to nobody: the receipt says ``clients: 0`` and nothing renders."""

_CARD_IMAGE_PREFIX = "/api/card-image/"
_CARD_IMAGE_PATTERN = "*/api/card-image/*"

PUSH_BUDGET_MS = 250
"""NFR-05 / SC-1. Stated here so the exit code and the printed line cannot disagree about it."""


def _read_token(data_dir: Path) -> str:
    """Read the live agent credential out of the discovery file the backend just wrote.

    The harness imports **nothing** from ``src/companion`` (this module's own contract, and c5-8's
    Q3 independence principle: a client bug and a backend bug must not be able to fail the same
    assertion), so the token is read from the file directly -- the same idiom ``cmd_budget`` uses.
    A token read from a *stale* or *different* data dir gets a 403 and measures nothing.
    """
    record = json.loads((data_dir / "companion.json").read_text(encoding="utf-8"))
    token: str = record["token"]
    return token


def _seeded_card_ids(companion_url: str, wanted: int) -> list[str]:
    """Return *wanted* real printing ids, read from the backend's own REST surface.

    Real Scryfall ids matter for the warm-art arm: ``/api/card-image/<id>`` only has bytes to warm
    for a card that exists. They are read over HTTP rather than out of ``cards.db`` so this stays a
    script that talks to the app, with no database driver and no ``src`` import.
    """
    decks = httpx.get(f"{companion_url}/api/decks", timeout=30).json()
    if not decks:
        raise SystemExit(
            "The data dir has no saved decks, so there are no real card ids to push. Point "
            "--data-dir at a copy of a data dir holding at least one deck, or pass --card-ids."
        )
    detail = httpx.get(f"{companion_url}/api/deck/{decks[0]['id']}", timeout=60).json()
    ids = [entry["card"]["id"] for entry in detail["cards"] if entry.get("card")]
    if not ids:
        raise SystemExit(f"Deck {decks[0]['id']} resolved no cards; nothing to push.")
    # Cycle rather than truncate: the 60-item worst case is deliberately allowed to repeat ids from
    # a smaller deck. Repeats are honest here -- the view renders each row independently and the
    # image cache is keyed per id, which is the same warmth a 60-distinct-id push would enjoy on
    # its second run.
    return [ids[index % len(ids)] for index in range(wanted)]


def _envelope(card_ids: list[str], *, run: int) -> dict[str, Any]:
    """Build one valid ``suggestions`` envelope (AD-6): ``{kind, id, ts, payload}``.

    The shape is the union member's, not an approximation of it: a malformed envelope answers 400
    and turns the whole run into a ``payload_rejected`` measurement of nothing (the story's own
    landmine 7).
    """
    return {
        "kind": "suggestions",
        "id": str(uuid.uuid4()),
        "ts": datetime.now(UTC).isoformat(),
        "payload": {
            "title": f"Cards worth a look (run {run})",
            "items": [
                {
                    "card_id": card_id,
                    "reason": f"Measured push {run}, row {index + 1}.",
                    "category": "Curve" if index == 0 else None,
                    "confidence": "high" if index == 0 else None,
                }
                for index, card_id in enumerate(card_ids)
            ],
        },
    }


def _await_page(browser: Browser, selector: str, timeout: float) -> bool:
    """Poll the page until *selector* exists. Polling is fine here -- this is a script, not a test.

    The polls are ``Runtime.evaluate`` round-trips and they add **no error** to the figure: every
    timestamp in the result was stamped in-page by the observer, never by this process.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if browser.js(f"!!document.querySelector({json.dumps(selector)})"):
            return True
        time.sleep(0.05)
    return False


def _await_surfaces(browser: Browser, timeout: float) -> dict[str, float]:
    """Poll until every named surface has been stamped, or the deadline passes."""
    deadline = time.time() + timeout
    surfaces: dict[str, float] = {}
    while time.time() < deadline:
        surfaces = browser.js("window.__surfaces") or {}
        if not set(PUSH_SURFACES) - set(surfaces):
            return surfaces
        time.sleep(0.05)
    return browser.js("window.__surfaces") or {}


def measure_push(
    browser: Browser,
    *,
    companion_url: str,
    token: str,
    card_ids: list[str],
    run: int,
    settle: float,
    image_settle: float,
) -> dict[str, Any]:
    """One measured push: POST the envelope, and ask the page when the view finished laying out.

    **The clock, and why it is a bracket rather than a stamp.** SC-1 says *within 250 ms of the
    tool call completing*, so t0 is the moment ``POST /agent/events`` returns -- the tool boundary
    in substance, since ``companion_show_suggestions`` is validation plus exactly this POST plus
    message mapping (``tools/companion.py:279-334``). That instant cannot be read from inside the
    page, so it is **bracketed** by two in-page ``performance.now()`` reads, one either side of the
    POST:

    * ``t_pre`` is stamped *before* the request is issued, so it is earlier than the true t0 by the
      whole POST. ``stop - t_pre`` therefore **over**-states the latency, and is the figure this
      harness reports and exits on. A budget met on this number is met on any honest reading.
    * ``t_post`` is stamped *after* the response lands, so it is later than the true t0 by one CDP
      round-trip and **under**-states the latency. It is recorded as SC-1's literal reading.

    The story spec proposed the ``t_post`` stamp alone and called its error conservative. Measured,
    it is the opposite: a stamp taken *after* t0 shrinks the measured window. Both ends are kept
    and the conservative one leads, so the direction of the error is a stated property rather than
    an assumption -- and the true figure is known to sit between the two.

    **Why DOM entry at commit is the honest "first paint of laid-out content".** The entering frame
    commits the *complete* layout at ``opacity: 0`` and the 480 ms bloom (``tokens.css:185``,
    ``AgentView.css:74-97``) is presentation on top of it (``AgentView.tsx:165-174``). So animation
    settle is outside this stop **by construction**, not by subtracting an animation duration from
    a larger number -- and under reduced motion the two coincide, exactly as NFR-05 says.
    """
    browser.js("window.__surfaces = {}")
    t_pre: float = browser.js("performance.now()")
    response = httpx.post(
        f"{companion_url}/agent/events",
        content=json.dumps(_envelope(card_ids, run=run)),
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json"},
        timeout=30,
    )
    t_post: float = browser.js("performance.now()")

    clients = response.json().get("clients") if response.status_code == 200 else None
    response_text = None if response.status_code == 200 else response.text[:200]
    surfaces = _await_surfaces(browser, settle)
    missing = sorted(set(PUSH_SURFACES) - set(surfaces))
    stop = max(surfaces.values()) if surfaces and not missing else None

    # THE IMAGE OBSERVATION IS TAKEN AFTER A SETTLE, AND THAT COSTS THE FIGURE NOTHING. A
    # `PerformanceResourceTiming` entry is published when the fetch *ends*, so reading the buffer
    # at the layout stamp counts zero requests every time -- measured, and the first draft of this
    # function reported a flawless "0 images off the network" on a stone-cold cache because of it.
    # Every timestamp in the result was stamped in-page by the observer before this sleep, so
    # waiting here cannot move `layout_ms`; it only lets the pictures finish arriving so their
    # warmth can be read honestly.
    time.sleep(image_settle)
    # A cached image still produces a resource-timing entry, with `transferSize` 0. Counting only
    # the entries that actually moved bytes is what tells a warm arm from a cold one -- landmine 5:
    # the browser cache and the backend's disk cache are two different warmths, and only the first
    # one is what the AC means by "warm image cache".
    images = browser.js(
        "performance.getEntriesByType('resource')"
        f".filter(e => e.name.includes({json.dumps(_CARD_IMAGE_PREFIX)}))"
        ".map(e => ({start: e.startTime, bytes: e.transferSize}))"
    )
    fresh = [entry for entry in images if entry["start"] >= t_pre]
    # The positive control for the whole arm: how many pictures actually painted. Without it a run
    # that fetched nothing because it rendered nothing would look identical to a perfectly warm one.
    settled = browser.js(
        "document.querySelectorAll('.suggestion-row-image[data-loaded=\"true\"]').length"
    )
    return {
        "run": run,
        "status_code": response.status_code,
        "response_text": response_text,
        "clients": clients,
        "surfaces": surfaces,
        "missing": missing,
        "observer_error": browser.js("window.__observerError"),
        "layout_ms": None if stop is None else stop - t_pre,
        "layout_from_return_ms": None if stop is None else stop - t_post,
        "bracket_ms": t_post - t_pre,
        "images_requested": len(fresh),
        "images_from_network": len([entry for entry in fresh if entry["bytes"]]),
        "images_painted": settled,
        "rows": browser.js("document.querySelectorAll('.suggestions-view-item').length"),
    }


def _open_measured_page(companion: Companion, args: argparse.Namespace, *, block: bool) -> Browser:
    """A fresh browser with the observer installed at document-start and the socket up."""
    browser = Browser(headless=not args.headed)
    browser.on_new_document(_OBSERVER.replace("__SELECTORS__", json.dumps(PUSH_SURFACES)))
    browser.send("Network.enable")
    if block:
        browser.block([_CARD_IMAGE_PATTERN])
    browser.navigate(companion.url, settle=args.settle)
    if not _await_page(browser, _SOCKET_LIVE, args.socket_wait):
        browser.close()
        raise SystemExit(
            "The page never reported a live socket, so a push would reach nobody. Check "
            f"{companion.log_path}."
        )
    return browser


def _reset_for_next_run(browser: Browser, args: argparse.Namespace) -> None:
    """Reload, keeping the HTTP cache, and wait for the socket again.

    A reload rather than a second push, because c6-6 ships replace-in-place: a repeat push reaches a
    view that is **already mounted**, so every surface was stamped by the previous push and the run
    would measure a replace instead of an open. ``ignore_cache=False`` is load-bearing for the warm
    arm -- the whole point is that the images stay in the browser's cache across the reset.
    """
    browser.reload(ignore_cache=False, settle=args.settle)
    if not _await_page(browser, _SOCKET_LIVE, args.socket_wait):
        raise SystemExit("The socket did not come back after a reload; refusing to measure.")


def cmd_push(args: argparse.Namespace) -> int:
    """Measure the push-to-render budget SC-1 states and nothing has ever observed (NFR-05).

    Three arms, and only the first is the acceptance criterion:

    * ``warm`` -- **the AC.** One discarded priming push warms the browser's image cache, then each
      measured run reloads (cache kept) and pushes once.
    * ``blocked`` -- **proves AC 5.** ``/api/card-image/*`` is failed at the transport, so the view
      must still lay out inside the budget on placeholders. "Never blocks on image fetches",
      observed rather than argued from the source.
    * ``cold`` -- **observation only.** A fresh profile per run, so every picture is a first fetch.
      NFR-05 excludes first-fetch image paint from the budget, so this number is context, not a
      verdict.
    """
    data_dir = Path(args.data_dir).resolve()
    companion = Companion(data_dir, args.port)
    companion.start()
    runs: list[dict[str, Any]] = []
    try:
        token = _read_token(data_dir)
        card_ids = (
            [value.strip() for value in args.card_ids.split(",") if value.strip()]
            if args.card_ids
            else _seeded_card_ids(companion.url, args.items)
        )
        print(f"companion on {companion.url}, data dir {data_dir}")
        print(f"arm {args.arm}, {len(card_ids)} item(s) per push, {args.runs} run(s)")

        fresh_browser_per_run = args.arm == "cold"
        browser = (
            None
            if fresh_browser_per_run
            else _open_measured_page(companion, args, block=args.arm == "blocked")
        )
        try:
            if args.arm == "warm" and browser is not None:
                # THE PRIMING PUSH, AND IT IS DISCARDED. Its only job is to put the pictures in the
                # browser's cache; its figure would be a cold measurement wearing a warm label.
                primer = measure_push(
                    browser,
                    companion_url=companion.url,
                    token=token,
                    card_ids=card_ids,
                    run=0,
                    settle=args.settle,
                    image_settle=args.image_settle,
                )
                print(
                    f"  prime: {primer['images_from_network']} image(s) fetched over the network"
                    f" ({primer['images_requested']} requested)"
                )
                time.sleep(args.prime_settle)

            for index in range(args.runs):
                if fresh_browser_per_run:
                    browser = _open_measured_page(companion, args, block=False)
                elif browser is not None:
                    _reset_for_next_run(browser, args)
                assert browser is not None
                result = measure_push(
                    browser,
                    companion_url=companion.url,
                    token=token,
                    card_ids=card_ids,
                    run=index + 1,
                    settle=args.settle,
                    image_settle=args.image_settle,
                )
                runs.append(result)
                _print_run(result)
                if fresh_browser_per_run:
                    browser.close()
                    browser = None
        finally:
            if browser is not None:
                browser.close()
    finally:
        companion.stop()

    return _report_push(runs, args)


def _print_run(result: dict[str, Any]) -> None:
    """One line per run -- a bad run says why, and never prints a number it does not have."""
    if result["status_code"] != 200:
        print(
            f"  run {result['run']}: INVALID -- POST /agent/events returned "
            f"{result['status_code']}: {result['response_text']}"
        )
        return
    if result["missing"]:
        why = result.get("observer_error") or "the view never rendered them"
        print(
            f"  run {result['run']}: INVALID -- surfaces never arrived: {result['missing']} ({why})"
        )
        return
    if not result["clients"]:
        print(f"  run {result['run']}: INVALID -- the receipt says clients={result['clients']}")
        return
    print(
        f"  run {result['run']}: layout {result['layout_ms']:.0f} ms"
        f" (from POST return {result['layout_from_return_ms']:.0f} ms,"
        f" bracket {result['bracket_ms']:.0f} ms)"
        f"  {result['rows']} row(s), {result['images_painted']} picture(s) painted,"
        f" {result['images_from_network']}/{result['images_requested']} off the network"
    )


def _report_push(runs: list[dict[str, Any]], args: argparse.Namespace) -> int:
    """Print the arm's figures, or refuse to print any. Exit code is the verdict."""
    good = [r for r in runs if not r["missing"] and r["clients"]]
    if not good:
        # The C4 trap, refused here as it is in `cmd_budget`: a run that measured nothing must not
        # be reported as a number. This is the branch plant 2 exists to fire.
        print("\nNO VALID RUNS -- refusing to report a number.", file=sys.stderr)
        return 1
    times = [r["layout_ms"] for r in good]
    literal = [r["layout_from_return_ms"] for r in good]
    print(
        f"\n{args.arm} arm, layout over {len(good)}/{len(runs)} valid runs: "
        f"min {min(times):.0f} / median {statistics.median(times):.0f} / max {max(times):.0f} ms"
        f"   (SC-1 budget: {PUSH_BUDGET_MS} ms; conservative bracket -- t0 stamped before the POST)"
    )
    print(
        "  SC-1's literal reading (t0 at the POST returning): "
        f"min {min(literal):.0f} / median {statistics.median(literal):.0f} / "
        f"max {max(literal):.0f} ms"
    )
    network = sorted({r["images_from_network"] for r in good})
    painted = sorted({r["images_painted"] for r in good})
    print(f"  card images fetched over the network per run: {network}")
    print(f"  card images painted per run: {painted}")
    if args.json:
        Path(args.json).write_text(json.dumps(runs, indent=2), encoding="utf-8")
        print(f"raw runs -> {args.json}")
    if args.arm == "cold":
        # Observation only: NFR-05 excludes first-fetch image paint, so this arm has no verdict to
        # give and must not be able to fail a run that is inside the spec.
        return 0
    return 0 if max(times) < PUSH_BUDGET_MS else 2


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

    push = sub.add_parser("push", help="measure the push-to-render budget (SC-1, NFR-05)")
    push.add_argument("--data-dir", required=True, help="data dir with a real cards.db and a deck")
    push.add_argument(
        "--arm",
        default="warm",
        choices=["warm", "cold", "blocked"],
        help="warm = the AC; blocked proves AC 5; cold is observation only",
    )
    push.add_argument("--runs", type=int, default=5, help="measured runs (c4-12 used 5)")
    push.add_argument("--items", type=int, default=6, help="suggestions per push (UJ-1 sends six)")
    push.add_argument(
        "--card-ids", default=None, help="comma-separated printing ids; default reads a saved deck"
    )
    push.add_argument("--settle", type=float, default=8.0, help="per-run deadline for the surfaces")
    push.add_argument("--prime-settle", type=float, default=3.0, help="wait after the warm primer")
    push.add_argument(
        "--image-settle",
        type=float,
        default=2.5,
        help="wait before reading image timings; does not affect layout_ms",
    )
    push.add_argument("--socket-wait", type=float, default=30.0)
    push.add_argument("--port", type=int, default=None)
    push.add_argument("--json", default=None, help="write raw per-run results here")
    push.add_argument("--headed", action="store_true")
    push.set_defaults(func=cmd_push)

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
