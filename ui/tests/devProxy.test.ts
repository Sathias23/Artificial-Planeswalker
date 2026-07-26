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
  it('proxies /api and /health with changeOrigin enabled', () => {
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

  it('does not yet proxy /ws — c5-6 adds it with the WebSocket client', () => {
    for (const pattern of Object.keys(createDevProxy({}, silent))) {
      expect(new RegExp(pattern).test('/ws')).toBe(false)
    }
  })
})
