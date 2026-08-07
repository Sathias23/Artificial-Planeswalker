/**
 * Where state is allowed to live, now that some exists (story c3-9, AC 18; Q1).
 *
 * ================= THE GAP THIS FILLS, MEASURED ========================================
 *
 * `tests/shell.test.ts` pins `AppShell.tsx` and the eight primitives to EXHAUSTIVE import lists
 * — nine hand-written lists, each naming its own directory. Measured at `16976c5`, that leaves
 * two holes this story walks straight into:
 *
 *   1. **A tenth primitive arrives with no list entry** and is covered by nothing. The lists are
 *      an enumeration of members, and this repo's standing ruling is *"ban the family, never
 *      enumerate members"* (C2 retro). Until c3-9 there was no state for a tenth primitive to
 *      reach for, so the enumeration cost nothing; there is now.
 *   2. **`src/App.tsx` is in neither list**, which was correct — it composes — and stays correct,
 *      because as of this story App is the one component that MAY hold state. What it may not do
 *      is fetch: the wire boundary is `src/api/`, and that is asserted below.
 *
 * So this file states the rule over the WHOLE tree rather than per directory. `shell.test.ts`'s
 * nine lists are untouched and still run — they say more about their nine files than this says
 * about any file, and deleting them to avoid overlap would trade a precise gate for a broad one.
 *
 * ================= THE RULE, AND WHY IT IS A DOOR RATHER THAN A BLOCKLIST ===============
 *
 * **A module under `src/components/` may take a TYPE from anywhere and a VALUE from nowhere but
 * its own tree and React.**
 *
 * That is what "presentation-only" means once it is said in a form that grows: types are erased
 * and cannot do anything, values are behaviour. It closes the aliasing evasion at the door
 * (`import { useSyncExternalStore as sync }` never matches a name-keyed regex, but it is still a
 * value import of React) and it needs no edit when a tenth primitive lands or when c4-1 adds a
 * second store slice — the new slice is simply somewhere a component may not import a value from.
 *
 * The syntax bans below are a SECOND layer, not the primary one, and they are deliberately keyed
 * on the identifier rather than on `identifier(` — `globalThis['fetch']` contains the word and
 * `globalThis['fet' + 'ch']` does not. **The declared residue: a computed global lookup assembled
 * from fragments defeats this file, and nothing here pretends otherwise.** `test_import_boundary`
 * makes the same declaration on the Python side — *"a guard satisfied by obfuscation is
 * theatre"* — and the answer to it is review, not a longer regex.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

// git is the file authority, not readdir: node_modules, dist and coverage are invisible to it,
// and a stray file is caught the moment it is committed — which is when CI sees it.
// DECLARED LIMIT (c4-7 review): an un-`git add`ed source is equally invisible, so a NEW file
// passes this sweep vacuously until staged; tree-walk redesign in deferred-work.md.
const trackedSources = execFileSync('git', ['ls-files', 'src'], { cwd: uiRoot, encoding: 'utf8' })
  .split('\n')
  .filter(Boolean)
  .filter((file) => /\.tsx?$/.test(file) && !/\.test\.tsx?$/.test(file))

const componentSources = trackedSources.filter((file) => file.startsWith('src/components/'))

/**
 * Comments removed, for the reason `shell.test.ts` removes them one file at a time: `states.ts`
 * documents that it contains no `setTimeout`, and a guard that reads documentation as code turns
 * red the moment somebody documents the rule properly.
 *
 * A WALK rather than a regex, because a regex stripper cannot tell a comment opener from data:
 * `const glob = '**\/*.css'` contains the two characters that open a block comment, and a blind
 * `.replace(/\/\*…\*\//)` would swallow everything from there to the next `*\/` — potentially a
 * `fetch(` call — leaving the guard silently blind. String and template contents are KEPT (the
 * import rules below read specifiers out of them); only comments are dropped. The residue this
 * walker declares, beside the computed-global one in the header: a REGEX LITERAL containing a
 * quote or `//` can still confuse it — distinguishing division from a regex needs a parser, and
 * the answer to that is review, not a longer walker.
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

/** Every module a source pulls in, with whether the import is type-only (and therefore erased). */
const importsOf = (
  source: string,
): readonly { readonly specifier: string; readonly typeOnly: boolean }[] =>
  [
    // `\(\s*` is the dynamic-import arm: `import('./x')` has no `from` clause and no space
    // after the keyword, so a pattern built for static imports alone walks straight past the
    // one form that loads a module at runtime rather than at parse time.
    ...source.matchAll(
      /\b(?:import|export)\s*(type\s+)?(?:[^'"]*?\bfrom\s+|\(\s*)?['"]([^'"]+)['"]/g,
    ),
  ].map((match) => ({ specifier: match[2], typeOnly: match[1] !== undefined }))

/**
 * Where a relative specifier lands, repo-relative. Bare specifiers (`react`, `zustand`) come back
 * unchanged, which is what the rules below discriminate on.
 *
 * `import { type X } from './y'` is NOT type-only here, and that is correct rather than strict:
 * `verbatimModuleSyntax` is on, so that form still emits the import and still runs the module.
 */
const resolveFrom = (file: string, specifier: string): string =>
  specifier.startsWith('.')
    ? path.posix.join(path.posix.dirname(file.replaceAll('\\', '/')), specifier)
    : specifier

/** The identifier families that ARE behaviour, keyed on the family and not on its members. */
const BEHAVIOUR_FAMILIES: readonly (readonly [string, RegExp])[] = [
  ['a network call', /\b(?:fetch|XMLHttpRequest|EventSource|WebSocket|navigator\.sendBeacon)\b/],
  ['a timer', /\b(?:setTimeout|setInterval|requestAnimationFrame|queueMicrotask)\b/],
  // React 19's `use()` is the one LOWERCASE hook, which a `use[A-Z]` prefix check waves through.
  ['a hook call', /\buse[A-Z]\w*\s*\(|(?<![\w.$])use\s*\(/],
]

describe('the guard is reading real files (non-vacuity)', () => {
  it('found the component tree and the modules outside it', () => {
    expect(componentSources.length).toBeGreaterThan(10)
    expect(componentSources).toContain('src/components/StatePanel/StatePanel.tsx')
    expect(trackedSources).toContain('src/App.tsx')
    expect(trackedSources).toContain('src/state/poller.ts')
  })

  it('strips comments without stripping code', () => {
    // The half that keeps the stripping honest: `states.ts` really does discuss `setTimeout` in
    // its prose, so a regression in the stripper would surface as a failure below rather than as
    // silence. Proving the raw file contains what the stripped file does not is what pins it.
    const raw = readFileSync(path.join(uiRoot, 'src/components/StatePanel/states.ts'), 'utf8')
    expect(raw).toMatch(/setTimeout/)
    expect(codeOf('src/components/StatePanel/states.ts')).not.toMatch(/setTimeout/)
    expect(codeOf('src/components/StatePanel/states.ts')).toMatch(/PANEL_FOR_REASON/)
  })

  it('does not let a string literal open a comment and swallow the code after it', () => {
    // The regression the walker replaced a regex to fix: `'**/*.css'` contains a block-comment
    // opener, and the old stripper deleted everything from there to the next `*/` — including,
    // here, a network call the family scan must keep seeing.
    const code = stripComments("const glob = '**/*.css'\nconst r = await fetch(DECKS_PATH)")
    expect(code).toContain('**/*.css')
    expect(code).toMatch(/\bfetch\b/)
    // …and a `//` inside a string is a path, not a line comment.
    expect(stripComments("const url = 'http://localhost:8000'\nsetTimeout(x, 1)")).toMatch(
      /setTimeout/,
    )
  })

  it('still strips both comment forms — the firing half of the walker (AC 26)', () => {
    expect(stripComments('// fetch(x)\nkeep')).toBe('\nkeep')
    expect(stripComments('/* setTimeout(y) */keep')).toBe('keep')
    // A comment opener as the LAST thing in the file must not hang or resurrect the text.
    expect(stripComments('keep /* unterminated')).toBe('keep ')
  })
})

describe('a component may take a TYPE from anywhere and a VALUE from its own tree (AC 18)', () => {
  /**
   * The one file allowed to import React VALUES, and the reason it exists at all: deciding
   * whether a Fragment is empty needs `isValidElement` and `Fragment`. c2-7 moved it up a
   * directory rather than carving an exception into a guard made blunt on purpose, and this
   * entry is that exception — named once, here, instead of widened into a rule.
   */
  const REACT_VALUES_ALLOWED = ['src/components/filled.ts']

  it.each(componentSources)('%s imports no value from outside the tree', (file) => {
    const offenders = importsOf(codeOf(file))
      .filter((entry) => !entry.typeOnly)
      .map((entry) => resolveFrom(file, entry.specifier))
      .filter((target) => target !== 'react' && !target.startsWith('src/components/'))

    // A store slice, a fetch helper, a poller or zustand itself would each land here. So would
    // `import('../../state/systemState')`, because a dynamic import is still a door.
    expect(offenders).toEqual([])
  })

  it.each(componentSources)('%s imports React as a TYPE only', (file) => {
    if (REACT_VALUES_ALLOWED.includes(file)) return
    const reactValueImports = importsOf(codeOf(file)).filter(
      (entry) => entry.specifier === 'react' && !entry.typeOnly,
    )
    // Hooks are value imports, so this one line closes every aliasing spelling at the door
    // instead of chasing names at the call site.
    expect(reactValueImports).toEqual([])
  })

  it('lets a component take a TYPE from outside — the silent half (AC 26)', () => {
    // `states.ts` imports `ErrorReason` from `src/api/schema` and always has. A rule that banned
    // all cross-tree imports would fail an existing, correct file, and its author would widen it
    // rather than obey it. Asserted so that the permission is deliberate rather than incidental.
    const crossTree = importsOf(codeOf('src/components/StatePanel/states.ts')).filter(
      (entry) => entry.typeOnly && !entry.specifier.startsWith('./'),
    )
    expect(crossTree.map((entry) => entry.specifier)).toContain('../../api/schema')
  })

  it.each([
    ['a store import', "import { useSystemStore } from '../../state/systemState'"],
    ['a dynamic import of one', "const s = await import('../../state/systemState')"],
    ['a value re-export', "export { readDecks } from '../../api/client'"],
    ['zustand itself', "import { create } from 'zustand'"],
    ['a fetch helper', "import { readDecks } from '../../api/client'"],
    ['the card cache', "import { hydrateCard } from '../../state/cards'"],
    // c4-4's Q1 ruling, and the reason the containers live OUTSIDE this tree rather than in a
    // second list inside it. This rule's filter is `!target.startsWith('src/components/')`, so
    // a stateful container that lived under `src/components/` would have had to be EXEMPTED —
    // and the exemption would have made this exact line invisible: a presentation-only
    // primitive rendering a component that holds state, takes handlers and holds a ref, with
    // every guard in the repo still green. Because `src/containers/` is a different root, the
    // rule that was already here catches it, with no new guard and no edit.
    [
      'a container, which is the c4-4 case',
      "import { CardTile } from '../../containers/CardTile/CardTile'",
    ],
  ])('would catch %s planted in the tree', (_label, line) => {
    // The FIRING half, fed inline the way every guard suite in this repo feeds its reader —
    // planting the breach in a real file and reverting it is what Task 9's probes do, and what
    // this pair exists so that they can confirm rather than discover.
    const offenders = importsOf(line)
      .filter((entry) => !entry.typeOnly)
      .map((entry) => resolveFrom('src/components/StatePanel/StatePanel.tsx', entry.specifier))
      .filter((target) => target !== 'react' && !target.startsWith('src/components/'))

    expect(offenders).not.toEqual([])
  })

  it.each([
    ['a plain hook import', "import { useState } from 'react'"],
    ['an ALIASED hook import', "import { useSyncExternalStore as sync } from 'react'"],
    ['a namespace import', "import * as React from 'react'"],
    ['a default import', "import React from 'react'"],
    ['a mixed import', "import React, { type ReactNode } from 'react'"],
    ['the inline-type form, which still runs the module', "import { type FC } from 'react'"],
  ])('would catch %s in a primitive', (_label, line) => {
    expect(
      importsOf(line).filter((entry) => entry.specifier === 'react' && !entry.typeOnly),
    ).not.toEqual([])
  })
})

describe('the component tree holds no behaviour, keyed on the family (AC 18)', () => {
  it.each(componentSources)('%s calls nothing that fetches, waits or holds state', (file) => {
    const code = codeOf(file)
    for (const [what, pattern] of BEHAVIOUR_FAMILIES) {
      expect(code, `${file} contains ${what}`).not.toMatch(pattern)
    }
  })

  it.each([
    ['a bare call', 'const r = await fetch(DECKS_PATH)'],
    ['a spaced call', 'const r = await fetch ("/api/decks")'],
    ['a window-qualified call', 'window.fetch("/api/decks")'],
    ['a computed global lookup', "globalThis['fetch']('/api/decks')"],
    ['a bare reference with no call', 'const f = fetch'],
    ['a socket', 'new WebSocket("/ws")'],
    ['a timer', 'setTimeout(poll, 2000)'],
    ['an rAF loop', 'requestAnimationFrame(poll)'],
    ['a capitalised hook', 'const [x, setX] = useState(0)'],
    ["React 19's lowercase use()", 'const value = use(promise)'],
    ['a spaced hook call', 'useEffect  (() => {}, [])'],
  ])('would catch %s planted in a component', (_label, line) => {
    // Spelled to EVADE, which is c3-3's headline finding made a habit: a guard keyed on the
    // syntax its own firing test uses caught 0 of 12 planted evasions. Two entries here are the
    // ones a `name(` regex misses and an identifier-keyed one does not — the computed lookup and
    // the bare reference with no call parens.
    //
    // ONE SPELLING IS DELIBERATELY ABSENT: an ALIASED hook call, `const v = sync(subscribe,
    // snapshot)`. No pattern over that line can know `sync` is `useSyncExternalStore`, and
    // pretending otherwise is how a guard becomes decoration. It is caught one layer up, at the
    // import door — `import { useSyncExternalStore as sync } from 'react'` is a React VALUE
    // import and fails the block above. That is why the door is the primary layer and this one
    // is the second.
    expect(
      BEHAVIOUR_FAMILIES.some(([, pattern]) => pattern.test(line)),
      `nothing catches: ${line}`,
    ).toBe(true)
  })

  it.each([
    ['ordinary prose in a class name', 'className="state-panel-decks"'],
    ['a use in a word', 'const because = "the user uses it"'],
    ['a property access spelled like a hook', 'const v = props.useless'],
    ['a method named after a member', 'copy.body.map((part) => part.text)'],
  ])('does not fire on %s — the silent half (AC 26)', (_label, line) => {
    expect(BEHAVIOUR_FAMILIES.some(([, pattern]) => pattern.test(line))).toBe(false)
  })
})

describe('there is exactly ONE door to the network in ui/src (AC 10, AC 18)', () => {
  const [, networkFamily] = BEHAVIOUR_FAMILIES[0]

  it('names it, and its name does not promise one route', () => {
    const doors = trackedSources.filter((file) => networkFamily.test(codeOf(file)))

    // Not "components do not fetch" — the whole SPA has one place a request is made, so the
    // retry rule, the `no-store` decision and the AC 10 no-path-parameter argument all have one
    // address. A second `fetch` anywhere else is a second spelling of the same thing and fails
    // here rather than in review.
    //
    // **This list read `['src/api/decks.ts']` until c4-1 (Q1), and the rename is the point.** The
    // property being asserted is "one door, named exhaustively", NOT "the door is called
    // `decks.ts`" — so when c4-1 added `GET /api/cards/{card_id}`, the choice was between a
    // second module (which fails this assertion by design, and would have meant weakening a
    // one-door rule into a per-directory one to buy a filename) and a module whose name stops
    // promising a single route. The second, and this line moved with it in the same commit as
    // the first card fetch. **The next route — c4-2's deck detail, c4-10's format check — goes
    // into the same file.**
    expect(doors).toEqual(['src/api/client.ts'])
  })

  it('does not let App itself become the second one', () => {
    // `src/App.tsx` is covered by neither of `shell.test.ts`'s nine lists, and as of this story
    // it MAY hold state — it calls a hook. What it may not do is reach the wire directly, which
    // is the boundary that would otherwise erode one convenient line at a time.
    const app = codeOf('src/App.tsx')
    expect(app).not.toMatch(networkFamily)
    // …and the non-vacuity half: it DOES consume the state, so this is a boundary rather than a
    // ban on a file that does nothing.
    expect(app).toMatch(/useSystemState\s*\(/)
  })
})
