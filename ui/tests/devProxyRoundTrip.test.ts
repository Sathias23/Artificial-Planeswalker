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

import { createServer as createViteServer } from 'vite'
import { afterEach, describe, expect, it } from 'vitest'

import { createDevProxy } from '../config/devProxy.ts'

/** A throwaway stand-in for the companion backend that records the Host header it is sent. */
interface StubBackend {
  server: Server
  port: number
  receivedHosts: string[]
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
  const server = createHttpServer((req, res) => {
    receivedHosts.push(req.headers.host ?? '<absent>')
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(JSON.stringify({ status: 'ok' }))
  })

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  openResources.push(() => new Promise<void>((resolve) => server.close(() => resolve())))

  return { server, port: (server.address() as AddressInfo).port, receivedHosts }
}

async function startViteProxying(
  targetPort: number,
  changeOrigin: boolean,
): Promise<{ origin: string }> {
  // The proxy entries come from the shipped factory, so this exercises the real config;
  // only `changeOrigin` is overridden, to produce the negative half of the pair.
  const proxy = Object.fromEntries(
    Object.entries(createDevProxy({ COMPANION_PORT: String(targetPort) })).map(([path, entry]) => [
      path,
      { ...entry, changeOrigin },
    ]),
  )

  const vite = await createViteServer({
    configFile: false,
    root: new URL('..', import.meta.url).pathname,
    logLevel: 'silent',
    server: { port: 0, host: '127.0.0.1', proxy },
  })

  await vite.listen()
  openResources.push(async () => {
    await vite.close()
  })

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
