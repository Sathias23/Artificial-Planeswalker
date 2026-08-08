/**
 * The Vite dev-server proxy to the companion backend.
 *
 * This module is the frontend's single declaration site for "where is the backend".
 * `vite.config.ts` consumes it; `tests/devProxy.test.ts` asserts the resolved config, and
 * `tests/devProxyRoundTrip.test.ts` drives this very object through a real Vite dev server
 * against a real HTTP listener — so the config that ships is the config under test.
 *
 * Why `changeOrigin` is not optional (C1 retro ruling R1, closing c1-5 Open Question 2):
 * the backend's `HostValidationMiddleware` compares the request's `Host` header against
 * `allowed_authorities(port)` — exactly `{"127.0.0.1:<backendPort>", "localhost:<backendPort>"}`
 * — with an exact match after lowercasing (see src/companion/app/security.py). A dev-time
 * request arrives at Vite on a *different* port, so without `changeOrigin: true` the proxied
 * request forwards Vite's authority, the comparison misses, and every single proxied call is
 * answered `400 {"reason": "invalid_request"}`. R1 accepted the second dev-time origin on
 * condition that this is asserted by a round trip rather than discovered in a browser.
 */

/** The env var the *backend* reads (src/companion/app/server.py :: PORT_ENV_VAR). One name, two processes. */
export const BACKEND_PORT_ENV_VAR = 'COMPANION_PORT'

/**
 * Mirrors `DEFAULT_PORT` in src/companion/app/server.py, which is the only place in `src/`
 * that names the number. This is the only place in `ui/` that names it.
 */
export const DEFAULT_BACKEND_PORT = 8765

/** Mirrors `_MIN_PORT` / `_MAX_PORT` in server.py. `0` is inside the range and means "assign me one". */
const MIN_PORT = 0
const MAX_PORT = 65535

/**
 * What Python's `int(str)` accepts in base 10, and nothing more.
 *
 * `Number()` is NOT a substitute and the difference is not academic — it is a split-brain
 * risk, because the backend parses the same variable with `int()`:
 *
 * | value     | Python `int()` | JS `Number()` | consequence if we used Number() |
 * | --------- | -------------- | ------------- | ------------------------------- |
 * | `"0x50"`  | ValueError → 8765 | 80         | frontend proxies 80, backend serves 8765 |
 * | `"1e3"`   | ValueError → 8765 | 1000       | frontend proxies 1000, backend serves 8765 |
 * | `"8_080"` | 8080           | NaN → 8765    | frontend proxies 8765, backend serves 8080 |
 *
 * Python also tolerates a sign and surrounding whitespace, both handled below. Underscores
 * are legal only *between* digits, never leading, trailing or doubled.
 *
 * ASCII only, knowingly: Python's `int()` additionally accepts Unicode decimal digits
 * (`int("８０８０")` is 8080), which `\d` rejects. Matching that here would buy an IME
 * artifact at the cost of a digit-normalization table, so the not-an-integer warning below
 * scopes its "the backend rejects this too" claim to ASCII instead of overclaiming.
 */
const PYTHON_BASE_10_INT = /^[+-]?\d+(?:_\d+)*$/

/**
 * Vite treats a key beginning with `^` as a RegExp source rather than a path prefix — and it
 * tests that regex against the FULL `req.url`, query string included. Both anchors therefore
 * admit a trailing `?…`: without that, `GET /health?verbose=1` fails `^/health$` at the `?`
 * and is served the SPA index.html with a 200 — a health probe answered by HTML that claims
 * success, which is strictly worse than the prefix-swallowing the anchors exist to prevent.
 */
const API_PATTERN = '^/api(?:[/?]|$)'
const HEALTH_PATTERN = '^/health(?:\\?|$)'

/**
 * The WebSocket upgrade, added by **c5-6** with the client that opens it.
 *
 * Anchored like the other two and for the same reason, with one extra trap this one walks past:
 * the real request is `GET /ws?ticket=<43 chars>` — `ws.py:97` takes the ticket as a query
 * parameter, because a browser `WebSocket` cannot set headers — so a pattern that stopped at `$`
 * would fail at the `?` and the upgrade would be answered with the SPA's index.html. That is the
 * `/health?verbose=1` failure the round-2 review already found once, on a path where it is
 * strictly harder to see: a socket that "just does not connect", with a 200 on the wire.
 */
const WS_PATTERN = '^/ws(?:[/?]|$)'

/**
 * The proxied surfaces, as anchored patterns rather than bare prefixes.
 *
 * A bare `'/api'` key is a **prefix** match in Vite, so it would also swallow a future
 * frontend route named `/api-docs`, and a bare `'/health'` would swallow `/healthcheck` —
 * silently, by forwarding them to a backend that has never heard of them. Anchoring costs
 * one regex each and removes the trap before any such route exists.
 */
export const PROXIED_PATTERNS = [API_PATTERN, HEALTH_PATTERN, WS_PATTERN] as const

/**
 * The subset that carries a WebSocket upgrade rather than a request/response (**c5-6**).
 *
 * Exported so `tests/devProxy.test.ts` asserts membership rather than re-typing the regex, and so
 * the two properties that only apply to a socket — `ws: true` and the `Origin` rewrite below —
 * are decided in one place instead of at each entry.
 */
export const WEBSOCKET_PATTERNS: readonly string[] = [WS_PATTERN]

/** A proxy entry as Vite consumes it. */
export interface DevProxyEntry {
  target: string
  changeOrigin: boolean
  /** Whether this entry proxies WebSocket upgrades. Absent (falsy) on the request/response ones. */
  ws?: boolean
  /** Request headers to overwrite on the way through. See {@link createDevProxy}. */
  headers?: Record<string, string>
}

/** Where a resolution warning goes. Overridable so tests can assert the warning is emitted. */
export type WarnSink = (message: string) => void

const consoleWarn: WarnSink = (message) => {
  console.warn(`[dev-proxy] ${message}`)
}

/**
 * Resolve the backend port from an environment mapping, mirroring the backend's own parser.
 *
 * Falls back to {@link DEFAULT_BACKEND_PORT} when the variable is unset or blank, and — like
 * `resolve_preferred_port` — when the value is not an integer in `0..65535`. Every fallback
 * that discards a value the user actually set is **warned about**, because the failure it
 * produces otherwise is a frontend and a backend disagreeing about a port with nothing on
 * screen to explain it.
 *
 * `0` is the one value that is legal for the backend and unusable here: it tells the backend
 * to take an ephemeral port, which a *static* dev-proxy config cannot know or follow. It is
 * therefore reported distinctly rather than being lumped in with typos.
 *
 * @param env - An environment mapping, typically `process.env`.
 * @param onWarn - Where to report a discarded value. Defaults to `console.warn`.
 */
export function resolveBackendPort(
  env: Record<string, string | undefined>,
  onWarn: WarnSink = consoleWarn,
): number {
  const raw = env[BACKEND_PORT_ENV_VAR]
  if (raw === undefined || raw.trim() === '') {
    return DEFAULT_BACKEND_PORT
  }

  const trimmed = raw.trim()

  if (!PYTHON_BASE_10_INT.test(trimmed)) {
    onWarn(
      `Ignoring ${BACKEND_PORT_ENV_VAR}=${JSON.stringify(raw)}: not a base-10 integer; using ` +
        `${DEFAULT_BACKEND_PORT}. The backend parses this variable with Python's int(), which ` +
        `rejects every ASCII spelling this check rejects — so both processes will use ` +
        `${DEFAULT_BACKEND_PORT}. (The one divergence: int() also accepts non-ASCII Unicode ` +
        `digits, this proxy does not. Spell the port in ASCII digits.)`,
    )
    return DEFAULT_BACKEND_PORT
  }

  const candidate = Number(trimmed.replace(/_/g, ''))

  if (candidate < MIN_PORT || candidate > MAX_PORT) {
    onWarn(
      `Ignoring ${BACKEND_PORT_ENV_VAR}=${JSON.stringify(raw)}: not in ${MIN_PORT}..${MAX_PORT}; ` +
        `using ${DEFAULT_BACKEND_PORT}. The backend ignores it too, for the same reason.`,
    )
    return DEFAULT_BACKEND_PORT
  }

  if (candidate === MIN_PORT) {
    onWarn(
      `${BACKEND_PORT_ENV_VAR}=0 tells the backend to bind an EPHEMERAL port, which this ` +
        `dev proxy cannot discover — it is configured once, before the backend starts. ` +
        `Proxying to ${DEFAULT_BACKEND_PORT} instead, which is almost certainly not where the ` +
        `backend is listening. Set a fixed port for the dev loop, or read the real port from ` +
        `the discovery file (companion.json) and set it explicitly.`,
    )
    return DEFAULT_BACKEND_PORT
  }

  return candidate
}

/** The backend's dev-time origin, e.g. `http://127.0.0.1:8765`. */
export function backendTarget(
  env: Record<string, string | undefined>,
  onWarn: WarnSink = consoleWarn,
): string {
  return `http://127.0.0.1:${resolveBackendPort(env, onWarn)}`
}

/**
 * Vite `server.proxy` config: every proxied pattern pointed at the backend, origin rewritten.
 *
 * ==== THE `/ws` ENTRY NEEDS A SECOND HEADER REWRITE, AND `changeOrigin` IS NOT IT =======
 * (c5-6, Q7, Brad 2026-08-08 — closing `deferred-work.md:5221-5237`, the Medium the ledger
 * recorded as *"slow to diagnose from the browser side"*.)
 *
 * `changeOrigin: true` rewrites **`Host`** and nothing else. That is exactly what the
 * `HostValidationMiddleware` needs and it is why every proxied `/api` call works — but a
 * WebSocket upgrade is checked TWICE, and by two different rules that `security.py`'s own
 * docstring insists are answering two different questions (*what did you address* against *who
 * is asking*):
 *
 *   | check | header | what a dev-time proxied upgrade sends without this |
 *   | Host   | `Host`   | rewritten by `changeOrigin` → the backend's authority → **passes** |
 *   | Origin | `Origin` | the browser's own — Vite's authority, e.g. `http://localhost:5173` → **fails** |
 *
 * `origin_is_allowed` compares against `{"http://127.0.0.1:<backendPort>",
 * "http://localhost:<backendPort>"}` by **exact match after lowercasing, with nothing parsed or
 * normalised** — so the port alone is enough to miss. The failure is `1008` pre-accept, rendered
 * as a bare `403` with no body and no reason token (`ws.py:29-40`, deliberately
 * indistinguishable from an expired ticket), which in a browser is a socket that closes with no
 * explanation at all. Every `/api` call keeps working, so nothing else on the page looks wrong.
 *
 * **Fix (a) of the three the ledger enumerated**, and the reason the other two lost:
 *
 *   - **(b) dial the backend port directly from the dev client** — makes dev and prod diverge
 *     inside `client.ts`, where `agentSocketUrl` derives the whole authority from
 *     `window.location` precisely so that it cannot.
 *   - **(c) widen `allowed_origins` behind a flag** — the ledger's own *"worst of the three"*: a
 *     bypass shipped in security code, live in the production build, to fix a dev-server problem.
 *
 * (a) keeps the backend check strict, ships no branch in `security.py`, and puts the entire
 * accommodation in a file that never reaches the bundle. It is exactly what `changeOrigin` does
 * for `Host`, applied to the second header — and `session.py`'s own docstring predicted this
 * repair by name: *"[checking Origin at the mint] would break any future Vite dev proxy that
 * rewrites `Host` but not `Origin`."*
 *
 * The header is written **only on the `/ws` entry**. The request/response routes have no `Origin`
 * check to satisfy (c5-2 Q1 ruled the mint deliberately origin-free), so rewriting theirs would
 * be an unrequested change to three working surfaces.
 */
export function createDevProxy(
  env: Record<string, string | undefined>,
  onWarn: WarnSink = consoleWarn,
): Record<string, DevProxyEntry> {
  const target = backendTarget(env, onWarn)
  return Object.fromEntries(
    PROXIED_PATTERNS.map((pattern) => [
      pattern,
      {
        target,
        // See the module docstring. Without this the backend answers 400 invalid_request.
        changeOrigin: true,
        ...(WEBSOCKET_PATTERNS.includes(pattern)
          ? {
              ws: true,
              // Lowercase key: Node normalises incoming header names to lowercase, and
              // http-proxy merges this map over them — a `Origin` key would ADD a second
              // header rather than replace the browser's.
              headers: { origin: target },
            }
          : {}),
      },
    ]),
  )
}
