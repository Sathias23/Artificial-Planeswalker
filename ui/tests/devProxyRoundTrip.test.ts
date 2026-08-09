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

import { createHash, randomBytes } from 'node:crypto'
import { createServer as createHttpServer, request as httpRequest, type Server } from 'node:http'
// `createServer` is no longer imported from here: the throwaway probe socket it opened was
// dw:5470's TOCTOU, removed at c5-8. Only the address type is still wanted.
import type { AddressInfo } from 'node:net'
import type { Duplex } from 'node:stream'
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

/**
 * A DISTINCT port per Vite server, with no probe and therefore no TOCTOU (dw:5470, paid at c5-8).
 *
 * ==== WHY DISTINCT PORTS ARE LOAD-BEARING, WHICH IS THE HALF THAT DID NOT CHANGE ========
 * Undici's fetch pools keep-alive sockets BY ORIGIN, so each test's first fetch could reuse a
 * stale socket to the previous test's just-closed server and die with ECONNRESET — an
 * intermittent, order-dependent flake (~1 in 3 runs once this file grew to five tests). Distinct
 * ports mean distinct origins mean no cross-test socket reuse. **That requirement is untouched.**
 *
 * ==== WHAT CHANGED: THE PROBE IS GONE ==================================================
 * This used to bind a throwaway `net` server on port 0, read the port the kernel assigned, close
 * it, and hand the number to Vite with `strictPort: true`. Between the close and Vite's bind sat a
 * genuine TOCTOU window, accepted at the time on the grounds that a collision would be *"a loud
 * EADDRINUSE, not a silent wrong-server test"*. It was loud, but it was not harmless: `c5-6`
 * sighted an intermittent vitest failure that cost one FILE its whole collection twice in 30 runs,
 * and the leading hypothesis was this window — a `listen` error raised outside any test's own
 * await is an "unhandled error", and it takes its file's collection with it. This story tripled
 * nothing itself, but it inherited the debt by name.
 *
 * The replacement removes the window rather than narrowing it: a monotonic counter supplies a
 * distinct STARTING port per server, and `strictPort: false` lets Vite bind-and-retry on
 * EADDRINUSE — one atomic step, with no gap for anyone to bind into. The real port is then read
 * back off `vite.httpServer.address()`, which this file already did for its return value, so the
 * caller's contract is unchanged.
 *
 * ⚠️ **`server.port: 0` is still not an option, and that was re-measured at c5-8 rather than
 * inherited from this comment's previous wording**: with `{ port: 0, strictPort: true }` Vite
 * treats the falsy 0 as "unset" and falls back to its 5173 default — measured directly against
 * the installed Vite by starting two servers, the second of which died with *"Port 5173 is
 * already in use"*. The counter exists because of that, not out of caution.
 *
 * The base sits well clear of Vite's own 5173 default so a developer's running dev server is not
 * the thing being collided with on every local run; a genuine collision is still resolved by the
 * retry rather than by this number being lucky.
 *
 * **The counter tracks the requested port, not the bound one — `reserveVitePortPastActual` closes
 * that gap (Greptile P1, caught on c5-8's PR).** If a retry ever moves a server onto a HIGHER port
 * than it was asked for, the next call here would otherwise hand out a port a still-live server
 * already holds; that collision resolves via ANOTHER retry, but the resulting real port can land
 * exactly on an earlier server's, which is a duplicate origin `recordOrigin()` correctly treats as
 * a failure. Every caller must re-seed the counter past whatever Vite actually bound.
 */
const VITE_PORT_BASE = 5310
let nextVitePort = VITE_PORT_BASE

function distinctVitePort(): number {
  const port = nextVitePort
  nextVitePort += 1
  return port
}

/** Re-seeds the counter past a port Vite actually bound, so a retry can never be handed out again. */
function reserveVitePortPastActual(boundPort: number): void {
  nextVitePort = Math.max(nextVitePort, boundPort + 1)
}

/**
 * Every origin this file has handed out, and the assertion that none repeats.
 *
 * The distinctness requirement was previously a PROPERTY OF A COMMENT: the probe returned a
 * kernel-assigned port, the comment explained why that mattered, and nothing checked it. Now that
 * the port is chosen by a counter and finally resolved by Vite's own retry, "distinct" is a claim
 * this file makes rather than one the kernel makes for it — so it is asserted at the one place
 * every server passes through. A repeat would resurrect the undici keep-alive ECONNRESET flake as
 * an intermittent failure somewhere else entirely; here it is an immediate, named one.
 */
const issuedOrigins = new Set<string>()

function recordOrigin(origin: string): string {
  expect(
    issuedOrigins.has(origin),
    `two Vite servers in this file were handed the same origin (${origin}); distinct origins are ` +
      `what stop undici reusing a keep-alive socket into a just-closed server`,
  ).toBe(false)
  issuedOrigins.add(origin)
  return origin
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
    // The proxy needs no dependency optimization, and leaving it on makes teardown
    // nondeterministic: serving index.html (the unproxied-path tests do) starts a dep
    // scan that `vite.close()` awaits — ~40s on a cold cache, against a 10s hook timeout.
    // The cache goes cold whenever the lockfile changes, so without this line every
    // dependency bump fails the NEXT local `npm test` once, unkillably (the timed-out
    // worker never persists the cache). Measured in review round 2.
    optimizeDeps: { noDiscovery: true },
    server: { port: distinctVitePort(), strictPort: false, host: '127.0.0.1', proxy },
  })

  // Same ordering rule as the stub above: a failed `listen()` must still be cleaned up.
  openResources.push(async () => {
    await vite.close()
  })
  await vite.listen()

  const address = vite.httpServer!.address() as AddressInfo
  reserveVitePortPastActual(address.port)
  return { origin: recordOrigin(`http://127.0.0.1:${address.port}`) }
}

/**
 * The same shipped config with the `/ws` entry's ORIGIN rewrite stripped out — the negative half
 * of c5-6's pair (AC 18, Q7).
 *
 * `startViteProxying` above overrides `changeOrigin` to produce its negative half; this one strips
 * `headers` for the same purpose and by the same rule: everything else comes from the real
 * factory, so what is being compared is one decision rather than two configurations.
 */
async function startViteProxyingWithoutOriginRewrite(targetPort: number): Promise<{
  origin: string
}> {
  const proxy = Object.fromEntries(
    Object.entries(
      createDevProxy({ COMPANION_PORT: String(targetPort) }, () => {
        /* a valid port never warns */
      }),
    ).map(([pattern, entry]) => {
      // Rebuilt rather than destructured-and-dropped: an unused binding is an eslint error, and
      // naming the omission is clearer than naming a variable nobody reads.
      const withoutHeaders = { ...entry }
      delete withoutHeaders.headers
      return [pattern, withoutHeaders]
    }),
  )

  const vite = await createViteServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    logLevel: 'silent',
    optimizeDeps: { noDiscovery: true },
    server: { port: distinctVitePort(), strictPort: false, host: '127.0.0.1', proxy },
  })

  openResources.push(async () => {
    await vite.close()
  })
  await vite.listen()

  const address = vite.httpServer!.address() as AddressInfo
  reserveVitePortPastActual(address.port)
  return { origin: recordOrigin(`http://127.0.0.1:${address.port}`) }
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

  // Vite tests the regex keys against the FULL req.url — query string included. Before the
  // round-2 patch, `^/health$` failed at the `?`, so `GET /health?verbose=1` was served the
  // SPA index.html with a 200: a health probe answered by HTML claiming success, with
  // nothing on screen to explain it.
  it('proxies bare paths carrying a query string', async () => {
    const backend = await startStubBackend()
    const { origin } = await startViteProxying(backend.port, true)

    await fetch(`${origin}/health?verbose=1`)
    await fetch(`${origin}/api?page=2`)

    expect(backend.receivedPaths).toEqual(['/health?verbose=1', '/api?page=2'])
  })
})

/**
 * The `/ws` entry, proven by a real upgrade rather than by reading a config object
 * (story c5-6, AC 18; Q7 — closing `deferred-work.md:5221-5237`).
 *
 * The C1 rule this file was written under applies to the new entry unchanged:
 * `entry.headers.origin === entry.target` is necessary and insufficient, and it is exactly the
 * vacuous shape the C1 retro punished twice. What matters is the byte on the wire — does the
 * backend receive an `Origin` its own `origin_is_allowed` accepts?
 *
 * The negative half of the pair is the whole point. Without the rewrite the forwarded `Origin` is
 * the BROWSER's, i.e. Vite's authority; `security.py:178-219` compares it against
 * `allowed_origins(port)` = {"http://127.0.0.1:<backendPort>", "http://localhost:<backendPort>"}
 * by exact match after lowercasing — **nothing is parsed or normalised**, so the port alone is
 * enough to miss — and `ws.py` refuses the handshake with close code `1008` pre-accept, rendered
 * to a browser as a bare `403` with no body and no reason token, deliberately indistinguishable
 * from an expired ticket. Every `/api` call on the same page keeps working. That is the "slow to
 * diagnose from the browser side" the ledger recorded, and this block is what stops it being
 * rediscovered there.
 *
 * ⚠️ **THE HANDSHAKE IS RAW `http.request`, NOT `new WebSocket(...)`, AND THAT IS A MEASUREMENT
 * RATHER THAN A STYLE.** Node 24 ships a global `WebSocket`, and the first draft of this block
 * used it — the negative test then recorded the forwarded Origin as `<absent>`, because Node's
 * client is not a browsing context and **sends no `Origin` header at all**. A test whose negative
 * half cannot reproduce the header under test is not a negative half. Raw upgrade requests let
 * this file present the exact header a browser would, which is also what `security.py`'s docstring
 * said c5-8's real client would have to do — and it did:
 * `tests/integration/companion/test_live_backend.py` passes `origin=` to `websockets.connect` for
 * exactly this reason, and a probe that removed it saw the real handshake refused 403.
 */
describe('dev proxy WebSocket upgrades (c5-6, AC 18)', () => {
  const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

  interface StubUpgradeBackend {
    port: number
    origins: string[]
    hosts: string[]
    paths: string[]
  }

  /** A stand-in for the companion's `/ws`, recording the upgrade headers and completing it. */
  async function startStubUpgradeBackend(): Promise<StubUpgradeBackend> {
    const origins: string[] = []
    const hosts: string[] = []
    const paths: string[] = []
    const server = createHttpServer((_req, res) => {
      res.writeHead(404)
      res.end()
    })

    // A REAL handshake, completed by hand: node ships no WebSocket SERVER, and computing the
    // accept token is five lines against pulling in a dependency `package-contract.test.ts`
    // would refuse anyway. What is under test is the proxy, not a socket library.
    // ⚠️ EVERY UPGRADED SOCKET IS TRACKED, AND THAT IS TEARDOWN RATHER THAN BOOKKEEPING. An
    // upgraded socket is DETACHED from the server's request lifecycle — it stays open by
    // definition, that being the point of a socket — so `server.close()` waits for it forever and
    // the `afterEach` above dies on its 10 s hook timeout with every assertion already green.
    // Measured here on the first run: three tests "failed" with no failed expectation between
    // them. The proxy holds one to the backend as well, so both ends are destroyed by hand.
    const upgraded: Duplex[] = []

    server.on('upgrade', (req, socket) => {
      upgraded.push(socket)
      origins.push(req.headers.origin ?? '<absent>')
      hosts.push(req.headers.host ?? '<absent>')
      paths.push(req.url ?? '<absent>')
      const accept = createHash('sha1')
        .update(`${req.headers['sec-websocket-key'] ?? ''}${GUID}`)
        .digest('base64')
      socket.write(
        'HTTP/1.1 101 Switching Protocols\r\n' +
          'Upgrade: websocket\r\n' +
          'Connection: Upgrade\r\n' +
          `Sec-WebSocket-Accept: ${accept}\r\n\r\n`,
      )
    })

    // Registered BEFORE listen, as every resource in this file is: a failed bind still leaves a
    // server object that needs closing.
    openResources.push(
      () =>
        new Promise<void>((resolve) => {
          for (const socket of upgraded.splice(0)) socket.destroy()
          server.closeAllConnections()
          server.close(() => resolve())
        }),
    )
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject)
      server.listen(0, '127.0.0.1', () => {
        server.off('error', reject)
        resolve()
      })
    })

    return { port: (server.address() as AddressInfo).port, origins, hosts, paths }
  }

  /**
   * Attempt one upgrade through the proxy, presenting `browserOrigin` exactly as a browser would.
   *
   * Resolves `'upgraded'` on a `101`, and `'refused'` on anything else — including the one-second
   * silence an unproxied path produces, which is a real outcome rather than a hang: Vite's own
   * HMR upgrade handler leaves a socket it does not recognise open, so a promise that only
   * settled on a response would sit until the suite timeout.
   */
  async function upgradeThrough(
    origin: string,
    path: string,
    browserOrigin: string,
  ): Promise<'upgraded' | 'refused'> {
    const url = new URL(path, origin)
    return await new Promise<'upgraded' | 'refused'>((resolve, reject) => {
      const request = httpRequest({
        hostname: url.hostname,
        port: url.port,
        path: `${url.pathname}${url.search}`,
        headers: {
          Connection: 'Upgrade',
          Upgrade: 'websocket',
          'Sec-WebSocket-Key': randomBytes(16).toString('base64'),
          'Sec-WebSocket-Version': '13',
          Origin: browserOrigin,
        },
      })
      request.on('upgrade', (_response, socket) => {
        socket.destroy()
        resolve('upgraded')
      })
      request.on('response', (response) => {
        response.resume()
        resolve('refused')
      })
      request.on('error', reject)
      request.setTimeout(1_000, () => {
        request.destroy()
        resolve('refused')
      })
      request.end()
    })
  }

  it('forwards the BACKEND origin, which is the byte the handshake is refused over', async () => {
    const backend = await startStubUpgradeBackend()
    const { origin } = await startViteProxying(backend.port, true)

    expect(await upgradeThrough(origin, '/ws?ticket=abc', origin)).toBe('upgraded')

    expect(backend.origins).toHaveLength(1)
    // This is the exact string `security.py :: allowed_origins` builds. Both halves matter: a
    // rewritten Origin carrying the wrong port fails identically to no rewrite at all.
    expect(backend.origins[0]).toBe(`http://127.0.0.1:${backend.port}`)
    // …and `changeOrigin`'s own header still arrives, because the upgrade is checked TWICE, by
    // two rules `security.py` insists are answering two different questions.
    expect(backend.hosts[0]).toBe(`127.0.0.1:${backend.port}`)
  })

  it('carries the ticket query string through untouched', async () => {
    const backend = await startStubUpgradeBackend()
    const { origin } = await startViteProxying(backend.port, true)

    await upgradeThrough(origin, '/ws?ticket=abc%20def', origin)

    // The ticket is the credential. A proxy that dropped or re-encoded the query would produce
    // exactly the same unexplained `1008` a forged ticket gets.
    expect(backend.paths).toEqual(['/ws?ticket=abc%20def'])
  })

  it('forwards the PAGE origin without the rewrite — the silent 403 this prevents', async () => {
    // The negative half, and the reason this file exists rather than a config assertion. Vite's
    // authority is not in `allowed_origins(backendPort)`; the port alone is enough to miss.
    const backend = await startStubUpgradeBackend()
    const { origin } = await startViteProxyingWithoutOriginRewrite(backend.port)

    await upgradeThrough(origin, '/ws?ticket=abc', origin)

    expect(backend.origins).toHaveLength(1)
    expect(backend.origins[0]).toBe(origin)
    // And the two really are different, or the assertion above proves nothing at all.
    expect(backend.origins[0]).not.toBe(`http://127.0.0.1:${backend.port}`)
  })

  it('does not upgrade a path that merely shares the /ws prefix', async () => {
    const backend = await startStubUpgradeBackend()
    const { origin } = await startViteProxying(backend.port, true)

    await upgradeThrough(origin, '/wsx', origin)

    // Anchored, not prefixed — the same trap `/api-docs` and `/healthcheck` already close, on the
    // one surface where the failure would present as "the socket just does not work".
    expect(backend.paths).toEqual([])
  })
})
