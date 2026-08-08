/**
 * The plain unit test half of AC 11, over the one piece of real logic the scaffold has:
 * resolving the backend's port from the environment (AC 12).
 *
 * The env var name is not retyped here from memory — it is imported from the module under
 * test, which documents src/companion/app/server.py :: PORT_ENV_VAR as its source.
 */

import { describe, expect, it } from 'vitest'

import {
  BACKEND_PORT_ENV_VAR,
  DEFAULT_BACKEND_PORT,
  PROXIED_PATTERNS,
  WEBSOCKET_PATTERNS,
  backendTarget,
  createDevProxy,
  resolveBackendPort,
} from '../config/devProxy.ts'

/** Collects warnings so every discarded value can be asserted to be loud, not silent. */
function withWarnings() {
  const warnings: string[] = []
  return { warnings, sink: (message: string) => warnings.push(message) }
}

const silent = () => {}

describe('resolveBackendPort', () => {
  it('falls back to the documented default when the variable is unset', () => {
    const { warnings, sink } = withWarnings()

    expect(resolveBackendPort({}, sink)).toBe(DEFAULT_BACKEND_PORT)
    expect(DEFAULT_BACKEND_PORT).toBe(8765)
    // An unset variable is the normal case, not a mistake — it must NOT warn.
    expect(warnings).toEqual([])
  })

  it('reads the same environment variable the backend reads', () => {
    expect(BACKEND_PORT_ENV_VAR).toBe('COMPANION_PORT')
    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: '9123' }, silent)).toBe(9123)
  })

  it.each([
    ['surrounding whitespace, as Python int() allows', '  9123  ', 9123],
    ['an explicit plus sign', '+9123', 9123],
    ['underscore separators, as Python int() allows', '8_080', 8080],
    ['multiple underscore groups', '1_0_0', 100],
  ])('accepts %s', (_label, raw, expected) => {
    const { warnings, sink } = withWarnings()

    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: raw }, sink)).toBe(expected)
    expect(warnings).toEqual([])
  })

  // These are the values where JS `Number()` and Python `int()` disagree. Using Number()
  // here would make the frontend proxy one port while the backend serves another, with
  // nothing on screen to explain it — so each one must fall back exactly as Python does.
  it.each([
    ['hex, which Number() would read as 80', '0x50'],
    ['exponent notation, which Number() would read as 1000', '1e3'],
    ['a float', '80.5'],
    ['non-numeric', 'not-a-port'],
    ['blank-but-present', '   '],
    ['a trailing underscore', '8080_'],
    ['a leading underscore', '_8080'],
  ])('rejects %s the way the backend does', (_label, raw) => {
    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: raw }, silent)).toBe(DEFAULT_BACKEND_PORT)
  })

  it.each([
    ['above the TCP range', '65536'],
    ['negative', '-1'],
  ])('ignores a value %s', (_label, raw) => {
    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: raw }, silent)).toBe(DEFAULT_BACKEND_PORT)
  })

  // A blank value is indistinguishable from "unset" and stays quiet; anything else the user
  // deliberately typed and we then discarded has to say so.
  it.each([['0x50'], ['1e3'], ['80.5'], ['not-a-port'], ['65536'], ['-1'], ['0']])(
    'warns loudly when discarding %s',
    (raw) => {
      const { warnings, sink } = withWarnings()

      resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: raw }, sink)

      expect(warnings).toHaveLength(1)
      expect(warnings[0]).toContain(BACKEND_PORT_ENV_VAR)
    },
  )

  // Port 0 is the one value that is LEGAL for the backend (server.py's _usable_port allows
  // it, meaning "assign me an ephemeral port") and unusable here, because a static proxy
  // config cannot discover the port the kernel hands out. Silently becoming 8765 is how a
  // developer spends an afternoon on a dev loop that cannot work.
  it('treats port 0 as a distinct, explained case rather than a typo', () => {
    const { warnings, sink } = withWarnings()

    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: '0' }, sink)).toBe(DEFAULT_BACKEND_PORT)
    expect(warnings).toHaveLength(1)
    expect(warnings[0]).toMatch(/ephemeral/i)
    expect(warnings[0]).toMatch(/companion\.json|discovery/i)
  })
})

describe('backendTarget', () => {
  it('always targets loopback by IPv4 literal', () => {
    expect(backendTarget({}, silent)).toBe('http://127.0.0.1:8765')
    expect(backendTarget({ [BACKEND_PORT_ENV_VAR]: '9123' }, silent)).toBe('http://127.0.0.1:9123')
  })
})

describe('createDevProxy (AC 12, AC 13 config half)', () => {
  it('proxies every declared surface with changeOrigin enabled', () => {
    // Two surfaces until c5-6, three since: `/api`, `/health` and `/ws`. Read off
    // `PROXIED_PATTERNS` rather than listed here, so the enumeration lives in one place and a
    // fourth surface arrives in this assertion by itself.
    const proxy = createDevProxy({}, silent)

    expect(Object.keys(proxy).sort()).toEqual([...PROXIED_PATTERNS].sort())
    for (const entry of Object.values(proxy)) {
      expect(entry.target).toBe('http://127.0.0.1:8765')
      expect(entry.changeOrigin).toBe(true)
    }
  })

  // Anchored patterns, not bare prefixes — Vite treats a plain string key as a prefix, which
  // would silently forward /api-docs and /healthcheck. The behavioural proof of this is in
  // devProxyRoundTrip.test.ts; here we only pin that the keys are regexes at all.
  it('uses anchored patterns so a shared prefix is not swallowed', () => {
    for (const pattern of Object.keys(createDevProxy({}, silent))) {
      expect(pattern.startsWith('^')).toBe(true)
    }

    const [apiPattern, healthPattern] = PROXIED_PATTERNS
    expect(new RegExp(apiPattern).test('/api/deck/1')).toBe(true)
    expect(new RegExp(apiPattern).test('/api')).toBe(true)
    expect(new RegExp(apiPattern).test('/api-docs')).toBe(false)
    expect(new RegExp(healthPattern).test('/health')).toBe(true)
    expect(new RegExp(healthPattern).test('/healthcheck')).toBe(false)

    // Vite matches the key against the FULL req.url, query string included — an anchor that
    // stops at `$` turns `GET /health?verbose=1` into SPA index.html with a 200 (review
    // round 2). The behavioural proof is in devProxyRoundTrip.test.ts; this pins the regex.
    expect(new RegExp(apiPattern).test('/api?page=2')).toBe(true)
    expect(new RegExp(apiPattern).test('/api/deck/1?fields=name')).toBe(true)
    expect(new RegExp(healthPattern).test('/health?verbose=1')).toBe(true)
  })

  /**
   * The `/ws` entry, added by c5-6 with the client that opens it (AC 18).
   *
   * This block REPLACES the `does not yet proxy /ws` assertion rather than sitting beside it. That
   * assertion named this story as its inheritor in its own title, and the property it protected —
   * *the proxy's surfaces are enumerated and nothing is proxied by accident* — is what the four
   * assertions below now state about three surfaces instead of two.
   */
  describe('the /ws entry (c5-6, AC 18; Q7)', () => {
    const ws = () => {
      const proxy = createDevProxy({}, silent)
      const pattern = Object.keys(proxy).find((key) => new RegExp(key).test('/ws'))
      expect(pattern, 'nothing proxies /ws').toBeDefined()
      return proxy[pattern!]
    }

    it('proxies /ws, and the ticket query string with it', () => {
      // The real request is `GET /ws?ticket=<43 chars>` — `ws.py:97` takes the ticket as a query
      // parameter because a browser socket cannot set headers. A pattern anchored at `$` fails at
      // the `?` and the upgrade is answered with the SPA's index.html: the `/health?verbose=1`
      // failure of review round 2, on a path where it presents as "the socket just doesn't work".
      const [pattern] = WEBSOCKET_PATTERNS
      expect(new RegExp(pattern).test('/ws')).toBe(true)
      expect(new RegExp(pattern).test('/ws?ticket=abc')).toBe(true)
      // …and still anchored, so a future frontend route is not swallowed.
      expect(new RegExp(pattern).test('/wsx')).toBe(false)
      expect(new RegExp(pattern).test('/wsocket')).toBe(false)
    })

    it('enables WebSocket proxying on that entry, and on no other', () => {
      // `ws: true` is what makes Vite forward the HTTP `upgrade` event at all. Without it the
      // pattern matches, the request is proxied as an ordinary GET, and the handshake never
      // completes — a failure with a 200 on the wire.
      expect(ws().ws).toBe(true)
      for (const [pattern, entry] of Object.entries(createDevProxy({}, silent))) {
        if (WEBSOCKET_PATTERNS.includes(pattern)) continue
        expect(entry.ws).toBeUndefined()
      }
    })

    it('rewrites ORIGIN as well as Host — the fix dw:5221 asked for (Q7)', () => {
      // `changeOrigin` rewrites `Host` and nothing else, and a WebSocket upgrade is checked
      // TWICE: `host_is_allowed` on the Host, `origin_is_allowed` on the Origin. The browser sets
      // Origin from the PAGE, which at dev time is Vite's authority — so without this line every
      // proxied handshake is refused `1008` pre-accept, rendered as a bare 403 with no body and
      // no reason token, while every `/api` call on the same page keeps working.
      const entry = ws()
      expect(entry.headers?.origin).toBe(entry.target)
      expect(entry.target).toBe('http://127.0.0.1:8765')
      // Lowercase key: Node normalises incoming header names, and http-proxy merges this map over
      // them — an `Origin` key would ADD a second header rather than replace the browser's.
      expect(Object.keys(entry.headers ?? {})).toEqual(['origin'])
    })

    it("leaves the request/response entries' Origin alone", () => {
      // The mint deliberately does NOT check Origin (c5-2 Q1: a cross-origin page can issue that
      // GET but cannot read its response), so rewriting the header on `/api` and `/health` would
      // be an unrequested change to two working surfaces.
      for (const [pattern, entry] of Object.entries(createDevProxy({}, silent))) {
        if (WEBSOCKET_PATTERNS.includes(pattern)) continue
        expect(entry.headers).toBeUndefined()
      }
    })

    it('follows the port everywhere, so the rewritten Origin is never the default by accident', () => {
      const proxy = createDevProxy({ [BACKEND_PORT_ENV_VAR]: '9123' }, silent)
      const pattern = Object.keys(proxy).find((key) => new RegExp(key).test('/ws'))!

      // The whole point of the rewrite is an EXACT match against `allowed_origins(port)` —
      // `origin_is_allowed` lowercases and compares, parsing and normalising nothing. A rewritten
      // Origin carrying the wrong port fails identically to no rewrite at all.
      expect(proxy[pattern].headers?.origin).toBe('http://127.0.0.1:9123')
    })
  })
})
