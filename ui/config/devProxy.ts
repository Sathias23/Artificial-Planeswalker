/**
 * The Vite dev-server proxy to the companion backend.
 *
 * This module is the frontend's single declaration site for "where is the backend".
 * `vite.config.ts` consumes it, and `tests/dev-proxy.test.ts` exercises the very same
 * object through a real Vite server, so the config that ships is the config under test.
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

/** Paths proxied to the backend in dev. `/ws` is deliberately absent — c5-6 adds it with the WebSocket client. */
export const PROXIED_PATHS = ['/api', '/health'] as const

/**
 * Resolve the backend port from an environment mapping.
 *
 * Falls back to {@link DEFAULT_BACKEND_PORT} when the variable is unset, blank, or not a
 * usable TCP port. Deliberately lenient in the same direction as the backend's own
 * `resolve_port`: a malformed value is ignored in favour of the default rather than
 * crashing the dev server.
 */
export function resolveBackendPort(env: Record<string, string | undefined>): number {
  const raw = env[BACKEND_PORT_ENV_VAR]
  if (raw === undefined || raw.trim() === '') {
    return DEFAULT_BACKEND_PORT
  }

  const candidate = Number(raw)
  if (!Number.isInteger(candidate) || candidate < 1 || candidate > 65535) {
    return DEFAULT_BACKEND_PORT
  }

  return candidate
}

/** The backend's dev-time origin, e.g. `http://127.0.0.1:8765`. */
export function backendTarget(env: Record<string, string | undefined>): string {
  return `http://127.0.0.1:${resolveBackendPort(env)}`
}

/** Vite `server.proxy` config: every proxied path pointed at the backend, origin rewritten. */
export function createDevProxy(
  env: Record<string, string | undefined>,
): Record<string, { target: string; changeOrigin: boolean }> {
  const target = backendTarget(env)
  return Object.fromEntries(
    PROXIED_PATHS.map((path) => [
      path,
      {
        target,
        // See the module docstring. Without this the backend answers 400 invalid_request.
        changeOrigin: true,
      },
    ]),
  )
}
