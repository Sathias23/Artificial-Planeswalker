/**
 * **Nothing on the glass mutates the deck** — the read-only-glass rule, as a gate (story c7-7).
 *
 * ================= THE GAP THIS FILLS, MEASURED =========================================
 *
 * The epic's context document states the rule in one line: *"Every state change must travel agent
 * → MCP tool → SQLite → notification → browser refetch."* Measured at `a4110a8`, three tests came
 * close to enforcing it and none of them did:
 *
 *   * `posture.test.ts:322-341` pins that exactly ONE module reaches the network. It says nothing
 *     about what that module is allowed to *send* — a `method: 'POST'` added to `client.ts`'s one
 *     `fetch` passes it untouched.
 *   * `store-writes.test.ts:152-154` pins that only `src/state/deck.ts` writes the deck store, and
 *     `:203-224` that the slice reads no third input. Both are about state arriving; neither is
 *     about a request leaving.
 *   * `shell.test.ts`'s nine import lists are per-directory enumerations of members, which this
 *     repo's standing ruling (C2 retro) says to prefer a family ban over.
 *
 * So the property held **by omission**: `grep "method:" ui/src` was empty because nobody had
 * written one, not because anything forbade it. That is the difference between a rule and a
 * coincidence, and adding a write affordance is the one change that collapses the product premise
 * (`EXPERIENCE.md`: *"the moment the glass grows write affordances, the product premise
 * collapses"*). One line of convenience — a "refresh" button that POSTs, a `<form>` around the
 * search box, a `sendBeacon` telemetry ping — would have shipped green.
 *
 * ================= THE RULE, AND WHY IT IS FIVE SPELLINGS RATHER THAN ONE ================
 *
 * **No shipped module under `ui/src` may spell a mutating request, in any of the five ways a
 * browser offers one.** They are genuinely different mechanisms rather than synonyms, which is why
 * banning `fetch` with a verb would not be enough:
 *
 *   1. `method:` — a request init carrying a verb. `fetch`'s, `Request`'s, and `axios`-shaped
 *      config objects all spell it identically, so the ban is keyed on the KEY and not on the
 *      function that receives it. (This is also the only rule that fires on a verb the SPA does
 *      not otherwise reach: `HEAD` and `OPTIONS` are as banned as `POST`, because a read that
 *      needs a verb is a read this app does not make.)
 *   2. `navigator.sendBeacon` — a POST that takes no init object at all and cannot be spelled with
 *      `method:`. It is the exact shape a telemetry or analytics addition arrives in.
 *   3. `FormData` — a multipart body. It has no other purpose in a client that only ever GETs.
 *   4. `<form` — the oldest write affordance on the web, and the one that needs no JavaScript to
 *      submit. A `<form>` in JSX is a navigation-away POST waiting for an Enter key, and neither
 *      the network guard nor the store guard can see it: it never touches `fetch` and never
 *      touches a store.
 *   5. `XMLHttpRequest.open(<verb>, …)` — the pre-`fetch` door, whose verb is a positional string
 *      argument rather than an init key. `posture.test.ts`'s network family already bans the
 *      identifier outright; this rule is the narrower, louder twin that names the verb, so a
 *      reviewer reading a failure sees *what was being sent* and not merely *that a door opened*.
 *   6. `.send(` — **the socket**, and the one the first five miss entirely. `client.ts` opens a
 *      real `WebSocket`, and a WebSocket is a two-way pipe: `socket.send(…)` carries no verb, no
 *      init object and no `fetch`, so every rule above walks straight past it while the page tells
 *      the backend to do something. The channel is deliberately one-way (AD-12: the store's inputs
 *      are REST responses and WebSocket *messages*), and this is what says so.
 *
 * ================= WHAT THIS CANNOT SEE, DECLARED =======================================
 *
 * **Declared, not claimed complete.** The six rules are the write affordances this codebase could
 * plausibly grow, not an enumeration of every byte a browser can be made to emit: an `<img
 * src={...}>` or a `<link>` pointed at a mutating URL is a GET with side effects and no pattern
 * here sees it, and neither does a service worker, a `Notification`, or an `iframe` posted to. The
 * repo's answer to that class is AD-2 — *the MCP server is the only writer* — enforced on the
 * BACKEND, where the routes are: `tests/unit/companion/test_import_boundary.py` pins that the
 * companion app has no write surface for a page to reach. This file is the frontend half of the
 * same property and is worth exactly what it covers.
 *
 * The same residue every text guard in this project declares, in the same words `posture.test.ts`
 * and `store-writes.test.ts` use: **a spelling assembled at runtime defeats it.**
 * `init['met' + 'hod'] = 'POST'` matches no pattern here, and `document.createElement('form')`
 * builds the banned element without the banned characters. No regex follows either; the answer is
 * review, not a longer pattern. What keeps the residue small is that every one of those spellings
 * is a review-visible oddity in a codebase where the ordinary one is three characters long.
 *
 * Second residue: the sweep is `git ls-files`, so an un-`git add`ed source is invisible until it is
 * staged — `posture.test.ts` declares the same limit for the same reason (git is the file authority
 * every guard here uses, so `node_modules`, `dist` and `coverage` cannot pass vacuously and a
 * committed file cannot escape CI).
 *
 * Third: **shipped source only.** `*.test.ts(x)` is excluded, because a future test that stubs a
 * backend and asserts on a request's verb is a legitimate thing to write and is not a write
 * affordance on the glass. AC 5's subject is *"the shipped frontend source"*, and that is what this
 * scans.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

// git is the file authority, not readdir — see the header's second declared residue.
//
// ⚠️ `index.html` IS IN THE SWEEP, and leaving it out was the first version's real hole: rule 4
// bans `<form`, and the shipped HTML document is the one file where a `<form>` needs no JavaScript
// at all to become a write affordance. It is Vite SOURCE that ships into
// `src/companion/app/static/index.html`, so it is exactly as shipped as any `.tsx` here. The
// pathspec shape is `tests/token-usage.test.ts:740-742`'s, which sweeps the same union for the
// same reason.
const shippedSources = execFileSync('git', ['ls-files', 'index.html', 'src'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((file) => /\.(?:tsx?|html)$/.test(file) && !/\.test\.tsx?$/.test(file))

/**
 * Comments removed, by a WALK rather than a regex — `posture.test.ts:159-187`'s stripper, verbatim
 * in behaviour and duplicated rather than imported.
 *
 * Duplicated because that module exports nothing (it is a test file, and turning it into a shared
 * helper module would move a guard's own machinery out of the file that documents it), and because
 * this file's own header names `method:` and `sendBeacon` in prose **eight times** — a guard that
 * read its own documentation as code would be red on the commit that created it. That is not a
 * hypothetical here the way it is elsewhere: it is why this stripper exists at all.
 *
 * The precedent for the duplication is the repo's own: `test_client.py`'s `_Sockets` is a
 * deliberate small duplicate of `test_server.py`'s `_Loopback`, ruled cheaper than the refactor.
 *
 * String and template contents are KEPT — a verb inside a string literal is exactly what rule 5
 * reads — and the walker's declared residue is unchanged: a REGEX LITERAL containing a quote or
 * `//` can still confuse it, because telling division from a regex needs a parser.
 *
 * **The direction of that residue is fail-SAFE, and it was measured rather than assumed.** The
 * worry it invites is c4-11's recorded failure: a `withoutComments` REGEX that ate a `' // '`
 * literal and, on another occasion, silently swallowed 4,700 characters of a component — under
 * which a ban passes vacuously because the code it was meant to see is gone. **This walker cannot
 * do that**, because it never deletes anything but comments: look at the string branch below, and
 * note that every character inside the span is appended to `out`. So a straight apostrophe in JSX
 * text (`<p>don't</p>`) opens a span that ends at the next apostrophe and copies everything in
 * between **verbatim** — nothing is lost, and the only consequence is that a comment *inside* that
 * span survives into the output, which can produce a false POSITIVE and never a false negative.
 * The anchors below prove both halves on real repo files and on that exact JSX case.
 */
const stripComments = (source: string): string => {
  let out = ''
  let index = 0
  while (index < source.length) {
    const pair = source.slice(index, index + 2)
    if (pair === '//') {
      while (index < source.length && source[index] !== '\n') index += 1
      continue
    }
    if (pair === '/*') {
      const close = source.indexOf('*/', index + 2)
      index = close === -1 ? source.length : close + 2
      continue
    }
    const char = source[index]
    if (char === '"' || char === "'" || char === '`') {
      out += char
      index += 1
      while (index < source.length && source[index] !== char) {
        if (source[index] === '\\') {
          out += source[index]
          index += 1
        }
        if (index < source.length) {
          out += source[index]
          index += 1
        }
      }
      if (index < source.length) {
        out += char
        index += 1
      }
      continue
    }
    out += char
    index += 1
  }
  return out
}

const codeOf = (file: string): string =>
  stripComments(readFileSync(path.join(uiRoot, file), 'utf8'))

/**
 * The five spellings of a mutating request, each with the line that MUST fire it and a line that
 * must NOT.
 *
 * The pairs are the per-rule non-vacuity anchor this project requires of every guard: a pattern
 * that stopped matching would report an empty offender list forever, which is indistinguishable
 * from a clean tree. `fires` proves the rule can still redden; `silent` proves it has not been
 * widened into something a story would disable within a week.
 */
const MUTATION_RULES: readonly {
  readonly what: string
  readonly pattern: RegExp
  readonly fires: readonly string[]
  readonly silent: readonly string[]
}[] = [
  {
    what: 'a request init carrying a verb',
    pattern: /\bmethod\s*:/,
    fires: [
      "await fetch(path, { method: 'POST', body })",
      'const init = { method : verb }',
      "new Request(path, {method:'DELETE'})",
    ],
    // `methodology` must not fire (the word boundary), and neither must a property ACCESS spelled
    // like the key — reading `request.method` off something is not sending one.
    silent: [
      'const m = response.method',
      "const methodology = 'read-only'",
      'type M = { method?: never }',
    ],
  },
  {
    what: 'a beacon (a POST with no init object to carry a verb)',
    pattern: /\bsendBeacon\b/,
    fires: ['navigator.sendBeacon(url, blob)', 'const send = navigator.sendBeacon'],
    silent: ['const beacon = 1', 'sendBeaconLike(x)'],
  },
  {
    what: 'a multipart body',
    pattern: /\bFormData\b/,
    fires: ['const body = new FormData()', 'let f: FormData'],
    silent: ['const formDataish = 1', 'type Formatted = string'],
  },
  {
    what: 'an HTML form (a write affordance that needs no JavaScript to submit)',
    // Case-insensitive: JSX admits `<Form>` as a component and HTML admits `<FORM>`. Both are the
    // banned element as far as a browser is concerned.
    pattern: /<form\b/i,
    fires: ['<form onSubmit={submit}>', '<FORM>', 'html += "<form action=/x>"'],
    // `<formatted/>` and a `<` that is a comparison must both stay quiet — the word boundary is
    // what separates the element from every identifier that starts with it.
    silent: ['<FormatCheck />', '<formatting/>', 'if (a<form_count) {}'],
  },
  {
    what: 'a socket write (the WebSocket carries no verb for the rules above to see)',
    // `.send` with a receiver, so `resend(x)` and a bare `send(` helper name do not fire; the
    // property is "nothing pushes anything back up the channel", and the channel is an object.
    pattern: /\.send\s*\(/,
    fires: ['socket.send(JSON.stringify(x))', 'this.ws.send(body)', 'sock.send ()'],
    silent: ['resend(x)', 'const s = sender.name', 'appended.sender'],
  },
  {
    what: 'an XMLHttpRequest opened with a verb',
    pattern: /\.open\s*\(\s*['"`]\s*(?:POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b/i,
    fires: ["xhr.open('POST', url)", 'request.open( "delete" , url)', 'x.open(`PATCH`, u)'],
    // `window.open` to a URL is a navigation, not a request with a verb; and a GET-shaped open is
    // still banned by `posture.test.ts`'s network family, which owns the identifier itself.
    silent: ["window.open('https://scryfall.com')", "xhr.open('GET', url)", 'dialog.open()'],
  },
]

describe('the guard is reading real files (non-vacuity)', () => {
  it('found the shipped frontend tree', () => {
    // An empty or truncated list would make every ban below pass by finding nothing — the failure
    // mode a wrong cwd or a git resolving the wrong tree produces.
    expect(shippedSources.length).toBeGreaterThan(50)
    expect(shippedSources).toContain('src/api/client.ts')
    expect(shippedSources).toContain('src/App.tsx')
    expect(shippedSources).toContain('src/state/deck.ts')
    // The shipped HTML document, which rule 4 exists for and an earlier sweep excluded.
    expect(shippedSources).toContain('index.html')
    // …and the exclusion really excludes: no test file is in the swept set (declared residue 3).
    expect(shippedSources.filter((file) => /\.test\.tsx?$/.test(file))).toEqual([])
  })

  it('strips comments without stripping code', () => {
    // This file's own header is the proof case: it names four of the six banned spellings in
    // prose. A stripper regression would make the bans below red on a clean tree — so the
    // stripping is asserted in both directions rather than assumed.
    expect(stripComments("// method: 'POST'\nkeep")).toBe('\nkeep')
    expect(stripComments('/* navigator.sendBeacon(x) */keep')).toBe('keep')
    expect(stripComments('keep /* unterminated')).toBe('keep ')
    // A string containing a comment opener must not swallow the code after it — the regression the
    // walker replaced a regex to fix.
    expect(stripComments("const g = '**/*.css'\nxhr.open('POST', u)")).toMatch(/\.open\('POST'/)
  })

  it('strips a REAL repo file, in both directions', () => {
    // `posture.test.ts`'s rule: a stripper proven only on synthetic strings is proven on strings
    // nobody ships. `src/api/types.d.ts` is the one shipped file that says a banned word in prose
    // — its JSDoc discusses a malformed request "aimed at a path/method/Host" — so it is the real
    // instance of exactly the confusion this stripper exists to remove.
    const raw = readFileSync(path.join(uiRoot, 'src/api/types.d.ts'), 'utf8')
    expect(raw, 'the anchor file no longer says the word in prose — pick another').toMatch(
      /path\/method\//,
    )
    expect(codeOf('src/api/types.d.ts')).not.toMatch(/path\/method\//)
    // …and the other direction, which is the half that matters more: real CODE survived. A
    // stripper that returned '' would pass the line above and every ban in this file.
    expect(codeOf('src/api/types.d.ts')).toMatch(/export/)
    expect(codeOf('src/api/client.ts')).toMatch(/\bfetch\s*\(/)
    expect(codeOf('src/api/client.ts')).toMatch(/AbortSignal/)
    expect(codeOf('index.html')).toMatch(/<div id="root">/)
  })

  it('does not let a straight apostrophe in JSX text swallow the code after it', () => {
    // THE c4-11 FAILURE CLASS, checked rather than assumed (see the stripper's docstring). A
    // regex-based stripper that DELETED string spans would lose everything between these two
    // apostrophes — including a banned spelling — and the bans would pass vacuously on that file.
    // This walker copies the span instead, so both survive and nothing is lost.
    const jsx = "<p>don't</p>\n<form onSubmit={x}>\nnavigator.sendBeacon(u)\n"
    const stripped = stripComments(jsx)
    expect(stripped).toBe(jsx)
    expect(stripped).toMatch(/<form\b/)
    expect(stripped).toMatch(/\bsendBeacon\b/)
  })

  it('leaves every shipped file with code in it — no file is silently emptied', () => {
    // The whole-tree version of the anchor above, and the cheapest guard against the 4,700-char
    // failure: a file whose stripped form is blank (or nearly) is one this guard has stopped
    // reading. Comments outweigh code in this codebase by design, so the floor is deliberately
    // low — it is looking for zero, not for a ratio.
    const emptied = shippedSources.filter((file) => codeOf(file).trim().length < 20)
    expect(emptied).toEqual([])
  })
})

describe('no shipped module under ui/src spells a mutating request (c7-7, AC 5)', () => {
  it.each(MUTATION_RULES)('bans $what', ({ pattern }) => {
    // Set equality against the empty list, so BOTH failure directions name themselves: the
    // offender list is the message, file by file, rather than a bare `false`.
    // THE FILE ALONE, WITHOUT A LINE NUMBER, AND THAT IS THE HONEST REPORT. An earlier version
    // counted newlines in the STRIPPED source — but `stripComments` deletes block comments
    // *including their newlines*, and this codebase's comments outweigh its code, so every number
    // it produced was wrong, usually by dozens of lines. A wrong line number in a guard failure is
    // worse than none: it sends the reader to an innocent line and makes them doubt the guard.
    const offenders = shippedSources.filter((file) => pattern.test(codeOf(file)))

    expect(offenders).toEqual([])
  })

  it.each(
    MUTATION_RULES.flatMap(({ what, pattern, fires }) =>
      fires.map((line) => ({ what, pattern, line })),
    ),
  )('would catch `$line` — the firing half of $what', ({ pattern, line }) => {
    expect(pattern.test(stripComments(line)), `nothing catches: ${line}`).toBe(true)
  })

  it.each(
    MUTATION_RULES.flatMap(({ what, pattern, silent }) =>
      silent.map((line) => ({ what, pattern, line })),
    ),
  )('says nothing about `$line` — the silent half of $what', ({ pattern, line }) => {
    // A guard that flagged the ordinary spellings would be disabled within a story, which is how a
    // gate becomes a comment.
    expect(pattern.test(stripComments(line))).toBe(false)
  })
})

describe('the one door to the network is a bare GET (c7-7, AC 5)', () => {
  const doorSource = codeOf('src/api/client.ts')

  /**
   * The balanced-paren argument text of the file's single `fetch(` call.
   *
   * Two corrections over the first draft, both of which made this pin softer than it looked:
   *
   * * the call is found by a **bounded regex**, not `indexOf('fetch(')` — `refetch(` and
   *   `prefetch(` both contain that substring, and either would have aimed the whole extraction at
   *   a different function while every assertion below carried on passing;
   * * the paren walk **skips string and template spans**, because a `)` inside a literal (a
   *   message, a path, a regex source) would close the slice early and leave the `not.toMatch`
   *   assertions reading a truncated fragment of the real init.
   */
  const fetchCall = (): string => {
    const call = /(?<![\w$.])fetch\s*\(/.exec(doorSource)
    expect(
      call,
      'the one door no longer contains a `fetch(` call — the pin is looking at nothing',
    ).not.toBeNull()
    const start = call!.index
    let depth = 0
    let quote: string | null = null
    for (let index = start + call![0].length - 1; index < doorSource.length; index += 1) {
      const char = doorSource[index]
      if (quote !== null) {
        if (char === '\\') index += 1
        else if (char === quote) quote = null
        continue
      }
      if (char === '"' || char === "'" || char === '`') {
        quote = char
        continue
      }
      if (char === '(') depth += 1
      if (char === ')') {
        depth -= 1
        if (depth === 0) return doorSource.slice(start, index + 1)
      }
    }
    throw new Error(
      'unbalanced parentheses in the fetch call — the extractor is looking at nothing',
    )
  }

  it('is the ONLY fetch in the file, and the extractor really found a call', () => {
    // The extractor's own non-vacuity: it returns a slice that starts at `fetch(` and ends with a
    // matching `)`, and that slice is the init the assertions below read.
    expect(fetchCall()).toMatch(/^fetch\s*\(/)
    expect(fetchCall().endsWith(')')).toBe(true)
  })

  it('is the only fetch in the file, and it is called exactly once', () => {
    // `posture.test.ts` proves `client.ts` is the only MODULE that reaches the network; this is the
    // narrower fact that guard cannot state — that the module holds one call rather than a family
    // of them, so "the door is a GET" is a claim about the whole door.
    expect([...doorSource.matchAll(/\bfetch\s*\(/g)]).toHaveLength(1)
  })

  it('hands its init NO verb, and the init is really there', () => {
    const call = fetchCall()
    // The negative: no verb, in any of the spellings the rules above ban.
    for (const { pattern } of MUTATION_RULES) expect(call).not.toMatch(pattern)
    // The positive, which is what makes the negative mean something: the init object EXISTS and
    // carries the three keys the door is documented to set. An extractor that silently grabbed
    // `fetch(path)` would satisfy every `not.toMatch` above while proving nothing at all.
    expect(call).toMatch(/\bcache\s*:/)
    expect(call).toMatch(/\bheaders\s*:/)
    expect(call).toMatch(/\bsignal\b/)
  })
})
