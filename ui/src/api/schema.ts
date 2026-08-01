/**
 * The one module that reads the generated wire types (AD-12, story c2-3 Decide-once #2).
 *
 * `types.d.ts` is generated verbatim from the backend's own `app.openapi()` and is shaped for a
 * generator, not for a reader: reaching a response body means indexing
 * `components['schemas'][…]` or `paths['/x']['get']['responses'][200]['content']['application/json']`.
 * Every module that does that for itself invents its own spelling of one shape, and four stories
 * later the same type has five names. So the indexing happens **here, once**, and the rest of
 * `ui/src` imports a narrow alias.
 *
 * Two rules, both enforced rather than documented:
 *
 * 1. **Nothing outside `src/api/` imports `./types` directly.** Add an alias below, then use the
 *    alias.
 * 2. **Nothing outside `src/api/` re-declares a shape the backend already describes** — no
 *    hand-written `interface HealthResponse`. `ui/tests/wire-contract.test.ts` reads the
 *    `components.schemas` keys out of the committed `openapi.json` and fails on any such
 *    declaration, so the rule grows on its own — it did exactly that when **c3-1** added the four
 *    deck models, with no edit to the test, and it will again when **c5-1** adds the event
 *    envelope.
 *
 * `import type` / `export type` only: `verbatimModuleSyntax` is on, and nothing about a `.d.ts`
 * may reach the runtime bundle.
 */

import type { components } from './types'

/** Every named shape in `components.schemas`, keyed by its Pydantic class name. */
type Schemas = components['schemas']

/**
 * The body of `GET /health` — the companion's unauthenticated identity probe (FR-14).
 *
 * `status` is a `'ok'` literal, not `string`: it is the closed token the backend's
 * `Literal["ok"]` declares, and `ui/src/api/schema.test.ts` pins it that way.
 */
export type HealthResponse = Schemas['HealthResponse']

/** The body of every non-2xx response: the reason token, and nothing else (AD-16). */
export type ErrorResponse = Schemas['ErrorResponse']

/**
 * The closed set of reason tokens (AD-16), as a TypeScript string union.
 *
 * Derived from `ErrorResponse` rather than re-listed, so a token added or removed on the Python
 * side arrives here through the generator instead of through someone remembering. This union is
 * what **c2-9**'s state panels switch on — a token silently dropped from it would compile fine and
 * lose a panel, which is why `schema.test.ts` pins every member by name. **Eight** as of c3-4
 * (`forbidden`); that file is the one place the count is written, so it is the one place a ninth
 * has to be added.
 *
 * Not every member reaches the glass, and that is by design rather than by omission: `forbidden`
 * and `payload_too_large` are answered to the **agent**, and `components/StatePanel/states.ts` is
 * where each token's destination — panel, placeholder, or deliberately nothing — is recorded in a
 * form the compiler checks.
 */
export type ErrorReason = ErrorResponse['reason']
