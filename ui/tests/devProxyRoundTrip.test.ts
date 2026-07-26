/**
 * Ruling R1, asserted by a real round trip rather than by reading a config object (AC 13).
 *
 * `createDevProxy(...).changeOrigin === true` is necessary and insufficient — it is exactly
 * the vacuous shape the C1 retro punished twice. What actually matters is the byte on the
 * wire: does the backend receive its OWN authority in the `Host` header?
 *
 * The second half of each pair is the whole point. With `changeOrigin: false` the forwarded
 * `Host` is Vite's authority; src/companion/app/security.py's `host_is_allowed` compares it
 * against `allowed_authorities(port)` = {"127.0.0.1:<backendPort>", "localhost:<backendPort>"}
 * by exact match, misses, and `HostValidationMiddleware` answers 400 {"reason":
 * "invalid_request"} for every proxied call. This test is what stops that being rediscovered
 * in a browser.
 *
 * Real servers over mocks — the standing C1 rule. The behaviour under test lives inside
 * Vite's proxy middleware, not in a config object, so both servers are real.
 */

import { createServer as createHttpServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { fileURLToPath } from 'node:url'

import { createServer as createViteServer } from 'vite'
import { afterEach, describe, expect, it } from 'vitest'

import { createDevProxy } from '../config/devProxy.ts'

/** A throwaway stand-in for the companion backend that records the Host header it is sent. */
interface StubBackend {
  server: Server
  port: number
  receivedHosts: string[]
  receivedPaths: string[]
}

const openResources: Array<() => Promise<void>> = []

afterEach(async () => {
  // A leaked Vite dev server keeps vitest from exiting and turns a fast suite into a hang,
  // so teardown is unconditional even when an expectation above it failed.
  const closers = openResources.splice(0)
  await Promise.all(closers.map((close) => close()))
})

async function startStubBackend(): Promise<StubBackend> {
  const receivedHosts: string[] = []
  const receivedPaths: string[] = []
  const server = createHttpServer((req, res) => {
    receivedHosts.push(req.headers.host ?? '<absent>')
    receivedPaths.push(req.url ?? '<absent>')
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ status: 'ok' }))
  })

  // Registered BEFORE listen: if the bind fails, the server object still exists and still
  // needs closing. Registering after would leak it on exactly the path that fails.
  openResources.push(() => new Promise<void>((resolve) => server.close(() => resolve())))

  await new Promise<void>((resolve, reject) => {
    // Without this the promise simply never settles on a bind error, and the failure
    // surfaces as an opaque test timeout instead of the actual EADDRINUSE/EACCES.
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      server.off('error', reject)
      resolve()
    })
  })

  return { server, port: (server.address() as AddressInfo).port, receivedHosts, receivedPaths }
}

async function startViteProxying(
  targetPort: number,
  changeOrigin: boolean,
): Promise<{ origin: string }> {
  // The proxy entries come from the shipped factory, so this exercises the real config;
  // only `changeOrigin` is overridden, to produce the negative half of the pair.
  const proxy = Object.fromEntries(
    Object.entries(
      createDevProxy({ COMPANION_PORT: String(targetPort) }, () => {
        /* a valid port never warns; silence keeps test output clean if that ever changes */
      }),
    ).map(([pattern, entry]) => [pattern, { ...entry, changeOrigin }]),
  )

  const vite = await createViteServer({
    configFile: false,
    // `fileURLToPath`, never `new URL(...).pathname` — on Windows the latter yields
    // "/C:/Users/..." which Vite resolves against the cwd into "C:\C:\Users\...", and it
    // also leaves %20 escapes in any path containing a space.
    root: fileURLToPath(new URL('..', import.meta.url)),
    logLevel: 'silent',
    server: { port: 0, host: '127.0.0.1', proxy },
  })

  // Same ordering rule as the stub above: a failed `listen()` must still be cleaned up.
  openResources.push(async () => {
    await vite.close()
  })
  await vite.listen()

  const address = vite.httpServer!.address() as AddressInfo
  return { origin: `http://127.0.0.1:${address.port}` }
}

describe('dev proxy Host rewriting (ruling R1, AC 13)', () => {
  it('forwards the BACKEND authority when changeOrigin is true', async () => {
    const backend = await startStubBackend()
    const { origin } = await startViteProxying(backend.port, true)

    const response = await fetch(`${origin}/health`)

    expect(response.status).toBe(200)
    expect(backend.receivedHosts).toHaveLength(1)
    // This is the exact string src/companion/app/security.py :: allowed_authorities builds.
    expect(backend.receivedHosts[0]).toBe(`127.0.0.1:${backend.port}`)
  })

  it('forwards the VITE authority when changeOrigin is false — the 400 this prevents', async () => {
    const backend = await startStubBackend()
    const { origin } = await startViteProxying(backend.port, false)
    const viteAuthority = new URL(origin).host

    const response = await fetch(`${origin}/health`)

    expect(response.status).toBe(200)
    expect(backend.receivedHosts).toHaveLength(1)
    expect(backend.receivedHosts[0]).toBe(viteAuthority)

    // And the two really are different, or the assertion above proves nothing at all.
    expect(viteAuthority).not.toBe(`127.0.0.1:${backend.port}`)
  })
})

describe('dev proxy path matching is anchored, not prefixed', () => {
  it('proxies the real surfaces', async () => {
    const backend = await startStubBackend()
    const { origin } = await startViteProxying(backend.port, true)

    await fetch(`${origin}/health`)
    await fetch(`${origin}/api/deck/1`)

    expect(backend.receivedPaths).toEqual(['/health', '/api/deck/1'])
  })

  // The non-vacuity pair, and the reason the patterns are regexes rather than bare prefixes:
  // Vite treats a plain string key as a PREFIX, so '/api' would swallow a future frontend
  // route called '/api-docs' and '/health' would swallow '/healthcheck' — forwarding them to
  // a backend that has never heard of them, with nothing on screen to explain the 404.
  it('does not proxy paths that merely share a prefix', async () => {
    const backend = await startStubBackend()
    const { origin } = await startViteProxying(backend.port, true)

    await fetch(`${origin}/healthcheck`)
    await fetch(`${origin}/api-docs`)

    expect(backend.receivedPaths).toEqual([])
  })
})
