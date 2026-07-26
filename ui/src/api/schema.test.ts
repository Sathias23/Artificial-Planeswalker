/**
 * The generated wire types, pinned by shape (AC 9).
 *
 * ⚠️ **`npm test` passing proves NOTHING about this file. `npm run typecheck` is the gate.**
 *
 * `expectTypeOf` assertions are erased at runtime — they compile to nothing and vitest executes an
 * empty test body. Measured on this project: mutate the generated `status: "ok"` to
 * `status: string` and `vitest run` still reports every test passing, while `tsc -b` exits 2 with
 * `error TS2344: Type '{ status: "ok"; … }' does not satisfy the constraint
 * '{ status: "Expected: literal string: ok, Actual: string"; … }'`.
 *
 * So do **not** "simplify" these into runtime assertions and do not treat a green vitest run as
 * evidence. Both gates run in CI (`typecheck` before `test`), which is what makes this file real.
 *
 * Why pin at all: without it, a regeneration that emitted an empty `types.d.ts` — a broken schema,
 * a generator flag change, a silently truncated file — would pass every gate this project has.
 * These assertions are the reason the drift checks guard something rather than guarding a file.
 */

import { describe, expectTypeOf, it } from 'vitest'

import type { ErrorReason, ErrorResponse, HealthResponse } from './schema'

describe('generated wire types (AD-12)', () => {
  // `status` must stay the 'ok' literal, not widen to string: it is the closed token the
  // backend's Literal["ok"] declares, and the identity probe's whole value is that a caller can
  // tell this companion from an unrelated server holding the same port (AD-4).
  it('pins HealthResponse to the backend shape', () => {
    expectTypeOf<HealthResponse>().toEqualTypeOf<{ status: 'ok'; instance_id: string }>()
  })

  // The body is the token and nothing else — no message, no detail, no errors[] (AD-16).
  it('pins ErrorResponse to the token and nothing else', () => {
    expectTypeOf<ErrorResponse>().toEqualTypeOf<{ reason: ErrorReason }>()
  })

  // All six named explicitly. This is the one assertion that cannot be derived from the generated
  // file, and that is the point: it is a second, independent statement of AD-16's closed set, so a
  // token dropped on the Python side reddens here instead of quietly deleting a c2-9 state panel.
  // Adding a seventh token (c3-2's card_not_found) is a deliberate act that edits this line.
  it('pins the closed six-token reason set', () => {
    expectTypeOf<ErrorReason>().toEqualTypeOf<
      | 'deck_not_found'
      | 'database_not_initialized'
      | 'database_unavailable'
      | 'invalid_request'
      | 'payload_too_large'
      | 'internal_error'
    >()
  })
})
