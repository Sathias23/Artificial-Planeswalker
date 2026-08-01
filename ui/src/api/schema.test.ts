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

  // All eight named explicitly. This is the one assertion that cannot be derived from the
  // generated file, and that is the point: it is a second, independent statement of AD-16's closed
  // set, so a token dropped on the Python side reddens here instead of quietly deleting a c2-9
  // state panel.
  //
  // c3-2 edited this line to add `card_not_found` and c3-4 to add `forbidden`, which is what the
  // previous two versions of this comment each predicted. The rule stands unchanged for a ninth:
  // adding a token is a deliberate act that edits this line — and `npm test` will NOT tell you
  // that you forgot, because this file's assertions erase to nothing at runtime (see the header).
  // The failure arrives from `npm run typecheck`, here and in `components/StatePanel/states.ts`.
  it('pins the closed eight-token reason set', () => {
    expectTypeOf<ErrorReason>().toEqualTypeOf<
      | 'deck_not_found'
      | 'card_not_found'
      | 'database_not_initialized'
      | 'database_unavailable'
      | 'invalid_request'
      | 'forbidden'
      | 'payload_too_large'
      | 'internal_error'
    >()
  })
})
