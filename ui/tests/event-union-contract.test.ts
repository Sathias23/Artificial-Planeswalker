/**
 * The generated event union, checked for the ONE property it was shaped to have (c5-1 Q1, c5-5).
 *
 * **Why this file exists now and could not have existed before.** c5-1 chose *a union of six
 * envelope classes* over *one envelope wrapping a payload union*, and the entire justification was
 * about the generated TypeScript: putting the discriminator on the envelope makes narrowing a
 * single step — `if (event.kind === 'swaps')` narrows `event.payload` too — where the alternative
 * puts `kind` one level above the union it selects, so a consumer narrows twice or casts once, in
 * every view, forever.
 *
 * That claim was unverifiable for four stories. A Pydantic model no route references never reaches
 * `components.schemas`, so until **c5-5** declared the union as `POST /agent/events`'s request
 * body there was no generated TypeScript to check it against. This is the first moment the
 * property is observable, so this is where it gets pinned.
 *
 * **Read against the committed `openapi.json`, not the live app** — the same seam
 * `wire-contract.test.ts` uses, and for the same reason: this asserts what was *shipped* to the
 * frontend. `test_openapi_contract.py` is the separate guard pinning shipped-equals-live, and the
 * ordering between them (regenerate, then assert) is ledgered in `deferred-work.md`.
 *
 * **No `ui/src` import anywhere in this file**, deliberately: it reads a JSON artifact, so it adds
 * nothing to the `tsc -b` project graph and cannot trigger the build cascade the ledger homes on a
 * `ui/tests` file that imports a src module with relative imports.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * Only the corners this file reads, typed by hand — the same stance `wire-contract.test.ts` takes.
 *
 * Not the generated `components` type from `../src/api/types`: a document-shape assertion must be
 * free to observe that the document is *wrong*, and typing it as the thing it is asserting about
 * would make several of these tests unwriteable. Hand-typing also keeps `JSON.parse`'s `any` from
 * leaking into every expression, which the lint gate refuses.
 */
interface JsonSchemaNode {
  $ref?: string
  const?: string
  enum?: string[]
  maxItems?: number
  description?: string
  properties?: Record<string, JsonSchemaNode>
  oneOf?: { $ref: string }[]
  discriminator?: { propertyName?: string }
  examples?: { kind?: string }[]
}

interface Operation {
  responses?: Record<string, { content?: Record<string, { schema?: JsonSchemaNode }> }>
  requestBody?: { content: Record<string, { schema: JsonSchemaNode }> }
  security?: unknown
}

interface OpenApiDocument {
  paths?: Record<string, Record<string, Operation>>
  components?: { schemas?: Record<string, JsonSchemaNode>; securitySchemes?: unknown }
}

const schema = JSON.parse(
  readFileSync(fileURLToPath(new URL('../src/api/openapi.json', import.meta.url)), 'utf8'),
) as OpenApiDocument

/** The ingest operation, or a hard failure — every test below depends on it existing. */
function operation(): Operation {
  const found = schema.paths?.['/agent/events']?.post
  if (!found) throw new Error('POST /agent/events is absent from the committed schema')
  return found
}

/** One named component, or a hard failure naming the missing shape. */
function component(name: string): JsonSchemaNode {
  const found = schema.components?.schemas?.[name]
  if (!found) throw new Error(`${name} is absent from components.schemas`)
  return found
}

/** One property of a named component, or a hard failure. */
function property(name: string, field: string): JsonSchemaNode {
  const found = component(name).properties?.[field]
  if (!found) throw new Error(`${name}.${field} is absent`)
  return found
}

/** The six envelope classes, hand-written in payload order — never derived from the document. */
const ENVELOPES = [
  'SuggestionsEvent',
  'SwapsEvent',
  'TierListEvent',
  'GroupsEvent',
  'DeckChangedEvent',
  'ActiveDeckChangedEvent',
] as const

/** The kind each envelope is tagged with, hand-written for the same reason. */
const KIND_BY_ENVELOPE: Record<string, string> = {
  SuggestionsEvent: 'suggestions',
  SwapsEvent: 'swaps',
  TierListEvent: 'tier_list',
  GroupsEvent: 'groups',
  DeckChangedEvent: 'deck_changed',
  ActiveDeckChangedEvent: 'active_deck_changed',
}

describe('the ingest operation is in the document at all', () => {
  it('declares POST /agent/events', () => {
    // Non-vacuity for everything below: read first, so a wrong-shaped parse cannot satisfy the
    // absence-flavoured assertions later by finding nothing.
    expect(operation()).toBeDefined()
    expect(Object.keys(schema.components?.schemas ?? {}).length).toBeGreaterThan(20)
  })

  it('answers with the receipt and nothing else on success', () => {
    const body = operation().responses?.['200']?.content?.['application/json']?.schema

    expect(body?.$ref).toMatch(/EventIngestReceipt$/)
    // The receipt carries the client count alone — no echo of the payload (CM-1).
    expect(Object.keys(component('EventIngestReceipt').properties ?? {})).toEqual(['clients'])
  })
})

describe('the request body narrows in one step', () => {
  it('is a oneOf over the six envelopes, each a $ref rather than an inline object', () => {
    const arms = operation().requestBody?.content['application/json'].schema.oneOf ?? []

    // Every arm a `$ref`: only a named model becomes a named TypeScript type, and an inline
    // object would produce a structural blob no consumer can name or narrow to.
    expect(arms.map((arm) => arm.$ref.split('/').pop())).toEqual([...ENVELOPES])
  })

  it('tags the discriminator on the ENVELOPE, so payload narrows with kind', () => {
    // THE PROPERTY c5-1 CHOSE THE SHAPE FOR. Each envelope carries `kind` as a single fixed value
    // *beside* its `payload`, so narrowing on `kind` narrows `payload` in the same step. Had the
    // union been one envelope over a payload union, `kind` would sit one level above the union it
    // selects and this assertion could not be written.
    //
    // Spelled `const`, not `enum` — measured 2026-08-08. Pydantic emits a single-valued `Literal`
    // as JSON Schema 2020-12's `const`, which openapi-typescript renders as a string-literal type;
    // that literal is what makes the narrowing work, so `const` is the right thing to assert and a
    // test looking for `enum` would have been a false red on a correct document.
    for (const name of ENVELOPES) {
      expect(property(name, 'kind').const, name).toBe(KIND_BY_ENVELOPE[name])
      expect(property(name, 'payload').$ref, name).toBeTruthy()
    }
  })

  it('gives every kind its own payload type rather than sharing one bag', () => {
    // A shared optional bag would let a `swaps` event carry tier items and still typecheck, which
    // is the failure the per-kind payload shapes exist to prevent.
    const payloads = ENVELOPES.map((name) => property(name, 'payload').$ref)

    expect(new Set(payloads).size).toBe(ENVELOPES.length)
  })

  it('declares a discriminator mapping the generator can key on', () => {
    // openapi-typescript does not require this to emit a usable union, but its presence is what
    // lets any other generator produce the same one-step narrowing.
    const requestSchema = operation().requestBody?.content['application/json'].schema

    expect(requestSchema?.discriminator?.propertyName).toBe('kind')
  })
})

describe('the shapes carry their documented constraints onto the wire', () => {
  it('publishes the item cap rather than leaving the list unbounded', () => {
    // The cap crosses the wire as `maxItems`; the AfterValidator behind it does not. A consumer
    // reading the generated types can therefore see the bound it will be refused for exceeding.
    expect(property('SuggestionsPayload', 'items').maxItems).toBe(60)
    expect(property('TierListPayload', 'items').maxItems).toBe(12)
  })

  it('ships a worked example for every envelope kind', () => {
    // c5-1's `json_schema_extra` examples reach `openapi.json` for the first time at c5-5. They
    // are what `/docs` renders and what an agent author copies, so an empty one is a real gap.
    for (const name of ENVELOPES) {
      const examples = component(name).examples ?? []

      expect(examples.length, name).toBeGreaterThan(0)
      expect(examples[0].kind, name).toBe(KIND_BY_ENVELOPE[name])
    }
  })

  it('keeps the docstring sections off the wire', () => {
    // `without_python_docstring_sections` truncates every description at its first Google-style
    // header, so `Attributes:` and doctest blocks stay on the Python side. Seventeen models
    // arrived at once here, which is the largest single opportunity for that truncator to have
    // been wrong.
    for (const name of ENVELOPES) {
      const description = component(name).description ?? ''

      expect(description, name).not.toContain('Attributes:')
      expect(description, name).not.toContain('>>>')
      // Non-vacuity: there is real prose that survived the truncation.
      expect(description.length, name).toBeGreaterThan(40)
    }
  })
})

describe('the operation declares exactly the failures it can produce', () => {
  it('names its four typed failures and no 503', () => {
    // No database dependency, so no 503 to promise; `payload_too_large` is declared because the
    // pre-parse cap makes it genuinely reachable here (c5-5, Q4).
    expect(Object.keys(operation().responses ?? {}).sort()).toEqual([
      '200',
      '400',
      '403',
      '413',
      '500',
    ])
  })

  it('is one of exactly two operations in the document declaring a 413', () => {
    // The curated wart: six body-less GETs used to publish an unreachable 413. After c5-5 only the
    // two body-bearing operations declare it, so a fetch author is never told to handle a branch
    // that cannot arrive.
    const declaring: string[] = []
    for (const [path, operations] of Object.entries(schema.paths ?? {})) {
      for (const [method, op] of Object.entries(operations)) {
        if (op.responses && '413' in op.responses) declaring.push(`${method} ${path}`)
      }
    }

    expect(declaring.sort()).toEqual(['post /agent/events', 'put /api/active-deck'])
  })

  it('documents no security scheme', () => {
    // The agent credential is read by hand inside a dependency precisely so the browser-facing
    // artifact never learns the name of a credential the browser must not hold (AD-5).
    expect(schema.components?.securitySchemes).toBeUndefined()
    expect(operation().security).toBeUndefined()
  })
})
