/**
 * The page's own port, as a string a sentence can carry.
 *
 * A module of its own rather than an export from `ConnectionPill.tsx`, for the mechanical
 * reason the lint rule states: a component file that also exports a helper breaks Fast
 * Refresh's whole-file replacement. And deliberately NOT in `copy.ts` — that module's charter
 * is authored words with a hard "what is data and not copy" line, and a port is data.
 *
 * From `window.location` and NEVER a configured number — the rule `agentSocketUrl` states for
 * the socket, applied to a tooltip: the SPA is served BY the companion (AD-13), so the page's
 * port IS the backend's port, whatever `COMPANION_PORT` chose. Any number written into this
 * bundle would be wrong for exactly the ephemeral-port case it was written for.
 */

/**
 * Resolve the page's port.
 *
 * `location.port` is the EMPTY string on a default-port URL, so the fallback names the default
 * the browser elided — `443` for `https:`, `80` otherwise — rather than showing "Port " with a
 * hole in it.
 *
 * Args:
 *   location: The page's location. Injectable for the fallback arms, which jsdom's fixed test
 *     URL cannot otherwise reach; production callers pass nothing.
 *
 * Returns:
 *   The port as text.
 */
export const pagePort = (
  location: Pick<Location, 'port' | 'protocol'> = window.location,
): string => {
  if (location.port !== '') return location.port
  return location.protocol === 'https:' ? '443' : '80'
}
