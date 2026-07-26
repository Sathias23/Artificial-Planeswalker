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
  backendTarget,
  createDevProxy,
  resolveBackendPort,
} from '../config/devProxy.ts'

describe('resolveBackendPort', () => {
  it('falls back to the documented default when the variable is unset', () => {
    expect(resolveBackendPort({})).toBe(DEFAULT_BACKEND_PORT)
    expect(DEFAULT_BACKEND_PORT).toBe(8765)
  })

  it('reads the same environment variable the backend reads', () => {
    expect(BACKEND_PORT_ENV_VAR).toBe('COMPANION_PORT')
    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: '9123' })).toBe(9123)
  })

  it.each([
    ['blank', '   '],
    ['non-numeric', 'not-a-port'],
    ['fractional', '80.5'],
    ['zero', '0'],
    ['above the TCP range', '65536'],
    ['negative', '-1'],
  ])('ignores a %s value in favour of the default', (_label, raw) => {
    expect(resolveBackendPort({ [BACKEND_PORT_ENV_VAR]: raw })).toBe(DEFAULT_BACKEND_PORT)
  })
})

describe('backendTarget', () => {
  it('always targets loopback by IPv4 literal', () => {
    expect(backendTarget({})).toBe('http://127.0.0.1:8765')
    expect(backendTarget({ [BACKEND_PORT_ENV_VAR]: '9123' })).toBe('http://127.0.0.1:9123')
  })
})

describe('createDevProxy (AC 12, AC 13 config half)', () => {
  it('proxies /api and /health with changeOrigin enabled', () => {
    const proxy = createDevProxy({})

    expect(Object.keys(proxy).sort()).toEqual(['/api', '/health'])
    for (const entry of Object.values(proxy)) {
      expect(entry.target).toBe('http://127.0.0.1:8765')
      expect(entry.changeOrigin).toBe(true)
    }
  })

  it('does not yet proxy /ws — c5-6 adds it with the WebSocket client', () => {
    expect(Object.keys(createDevProxy({}))).not.toContain('/ws')
  })
})
