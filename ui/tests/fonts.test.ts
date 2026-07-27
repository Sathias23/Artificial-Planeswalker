/**
 * The typeface is a BINARY, and every other gate in this project reasons about text.
 *
 * Three separate things have to be true before "the app renders in Space Grotesk offline" is a
 * fact rather than a hope, and all three fail in ways that look identical in a browser — the
 * text renders in `system-ui` and nothing anywhere says why:
 *
 *   1. THE BYTES SURVIVED GIT. core.autocrlf is `true` on the maintainer's machine. Without a
 *      `binary` attribute a .woff2 is line-ending-normalised on checkout, on Windows only, on a
 *      fresh clone — the same silent, platform-specific corruption c2-2 measured for index.html
 *      and could only find by counting bytes. So the signature is checked, and so is the
 *      ATTRIBUTE that keeps it correct on a machine this suite never runs on.
 *   2. NOTHING REACHES A CDN. The design system this project imports ships its fonts as a
 *      Google Fonts @import, and measured at the baseline commit, NOTHING in either lint layer
 *      objected to one — a file containing only that @import lints exit 0. The offline
 *      guarantee (UX-DR2, NFR-06) therefore needs a guard of its own, over the built bundle.
 *   3. THE @font-face IS THE ONLY ONE. A value-level rule bans a component from CONSUMING a
 *      second family; it cannot see a component that DECLARES one. @font-face is confined here.
 *
 * WHAT THIS FILE CANNOT PROVE, STATED UP FRONT. That the glyphs on screen are Space Grotesk.
 * jsdom does not load fonts, does not apply @font-face, and reports back whatever family string
 * it was handed — so a getComputedStyle assertion here would pass on a corrupt font, a missing
 * font and a 404, which makes it worse than no assertion at all. That half is a browser check
 * with the network throttled to offline, and it is on the epic's manual-testing checklist.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const repoRoot = fileURLToPath(new URL('../..', import.meta.url))
const fixture = (rel: string) => fileURLToPath(new URL(`fixtures/${rel}`, import.meta.url))

/** The committed binary, and the stylesheet that is the only file allowed to name it. */
const FONT_FILE = 'src/assets/fonts/space-grotesk-latin-wght-normal.woff2'
const LICENCE_FILE = 'src/assets/fonts/LICENSE-OFL-1.1.txt'
const FONT_STYLESHEET = 'src/styles/fonts.css'

/** The committed SPA bundle (AD-13), relative to the repository root, not to ui/. */
const BUNDLE = 'src/companion/app/static'

const git = (...args: string[]) => execFileSync('git', args, { cwd: uiRoot, encoding: 'utf8' })

// ---------------------------------------------------------------------------------------
// AC 2 — the binary is provably a real WOFF2, and provably protected from normalisation
// ---------------------------------------------------------------------------------------

describe('the committed font binary (AC 2, AC 3)', () => {
  // git ls-files, not existsSync. An UNTRACKED font passes every byte check below while being
  // invisible to CI, to a fresh clone and to the `plugin/` mirror — the exact trap c2-4 hit
  // when an unstaged tokens.css made a guard vacuous. Tracked-ness is the first assertion.
  const tracked = git('ls-files', 'src/assets/fonts').split('\n').filter(Boolean)

  it('is tracked by git, alongside its licence', () => {
    expect(tracked).toContain(FONT_FILE)
    expect(tracked).toContain(LICENCE_FILE)
    expect(tracked).toHaveLength(2)
  })

  it('is a real WOFF2 — signature and size, not a hopeful filename', () => {
    const bytes = readFileSync(join(uiRoot, FONT_FILE))

    // `wOF2`. A WOFF1 file says `wOFF`, a bare TTF says \0\1\0\0, and a git-normalised WOFF2
    // still says `wOF2` at byte 0 while being corrupt further in — which is why the SIZE is
    // asserted too: CRLF normalisation changes the length of the file, and this one is exact.
    expect(bytes.subarray(0, 4).toString('latin1')).toBe('wOF2')
    expect(bytes.length).toBeGreaterThan(10 * 1024)
    // The exact published size of @fontsource-variable/space-grotesk@5.3.0's latin subset.
    // Byte-exact rather than a range: any normalisation at all moves this number.
    expect(bytes.length).toBe(22288)

    // WOFF2's header stores the DECOMPRESSED sfnt length at offset 16 (big-endian uint32).
    // A truncated or mangled file fails here even when the four magic bytes survive.
    expect(bytes.readUInt32BE(16)).toBeGreaterThan(bytes.length)
  })

  it('is declared binary to git, so a Windows checkout cannot normalise it', () => {
    // The assertion that protects a machine this suite never runs on. CI is ubuntu, where
    // core.autocrlf is off and the corruption is unreachable; the maintainer's Windows box has
    // it `true`. Asking git what attributes RESOLVE for the path tests the outcome rather than
    // the spelling of any one .gitattributes line, so moving the rule between files is safe
    // and deleting it is not.
    const attributes = git('check-attr', 'text', 'diff', '--', FONT_FILE)
    expect(attributes).toContain('text: unset')
    expect(attributes).toContain('diff: unset')
  })

  it('ships the OFL-1.1 licence text beside it, with the attribution OFL requires', () => {
    const licence = readFileSync(join(uiRoot, LICENCE_FILE), 'utf8')
    expect(licence).toContain('SIL OPEN FONT LICENSE Version 1.1')
    expect(licence).toContain('The Space Grotesk Project Authors')
    // c2-10 owns the footer; this story owes it the file and the fact. If the copyright line
    // ever stops being reachable from here, that story's attribution has no source.
    expect(readFileSync(join(uiRoot, FONT_STYLESHEET), 'utf8')).toContain(
      'The Space Grotesk Project Authors',
    )
  })
})

// ---------------------------------------------------------------------------------------
// AC 6 — the @font-face itself
// ---------------------------------------------------------------------------------------

describe('the @font-face (AC 6, AC 11b)', () => {
  const fontCss = readFileSync(join(uiRoot, FONT_STYLESHEET), 'utf8')

  /** `src: url('…')` — the URL, unquoted, whatever quote style was used. */
  const srcUrl = /src:\s*url\(\s*['"]?([^'")]+)['"]?\s*\)/.exec(fontCss)?.[1]

  it('points at the committed binary by a RELATIVE url the bundler can resolve', () => {
    expect(srcUrl, 'no src: url() found in the font stylesheet at all').toBeDefined()
    // Relative, so the bundle is position-independent and Vite can content-hash the target.
    // An absolute path (`/src/assets/…`) survives dev and breaks the hashing; an origin
    // (`https://…`) is the CDN this story exists to remove.
    expect(srcUrl!.startsWith('./') || srcUrl!.startsWith('../')).toBe(true)
    expect(srcUrl).not.toMatch(/^(https?:)?\/\//)
    // …and it resolves to the file that is actually committed.
    expect(join(uiRoot, 'src/styles', srcUrl!)).toBe(join(uiRoot, FONT_FILE))
  })

  it('declares the whole variable weight axis, so one file serves all seven roles', () => {
    // DESIGN.md's roles are 400, 500 and 700. A single static weight here would make four of
    // the seven synthesise — faux-bold, which is a different typeface wearing the same name.
    expect(fontCss).toMatch(/font-weight:\s*300\s+700/)
    expect(fontCss).toMatch(/format\(\s*['"]woff2['"]\s*\)/)
    expect(fontCss).toMatch(/font-display:\s*swap/)
  })

  it('declares the subset range the file actually contains, copied not invented', () => {
    // Verbatim from @fontsource-variable/space-grotesk@5.3.0's own wght.css. A range WIDER
    // than the file's real coverage is worse than none: the browser stops falling back for
    // the characters the font lacks and renders .notdef boxes instead of system-ui.
    const range = /unicode-range:\s*([^;]+);/.exec(fontCss)?.[1]
    expect(range, 'the @font-face declares no unicode-range').toBeDefined()
    const declared = range!.split(',').map((r) => r.trim().toUpperCase())
    expect(declared).toEqual([
      'U+0000-00FF',
      'U+0131',
      'U+0152-0153',
      'U+02BB-02BC',
      'U+02C6',
      'U+02DA',
      'U+02DC',
      'U+0304',
      'U+0308',
      'U+0329',
      'U+2000-206F',
      'U+20AC',
      'U+2122',
      'U+2191',
      'U+2193',
      'U+2212',
      'U+2215',
      'U+FEFF',
      'U+FFFD',
    ])
  })

  it('names the family the token names — the join that makes --font-sans real', () => {
    // If these two strings ever diverge, --font-sans falls through to system-ui and every
    // other assertion in this file still passes. tokens.test.ts pins the token side.
    expect(fontCss).toMatch(/font-family:\s*'Space Grotesk'/)
    expect(readFileSync(join(uiRoot, 'src/styles/tokens.css'), 'utf8')).toContain(
      "--font-sans: 'Space Grotesk'",
    )
  })
})

/**
 * AC 11b — @font-face is a DECLARATION, so no value-level rule can see it.
 *
 * The typography-literal ban in .stylelintrc.json stops a component using a second family.
 * It cannot stop a component SHIPPING one: `@font-face { font-family: 'Comic Sans'; src: … }`
 * introduces a whole typeface while consuming nothing, and every value rule stays silent. This
 * is the same shape as c2-4's "no component may declare a token", and fails the same way.
 */
const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '')

const findStrayFontFaces = (files: string[], read: (f: string) => string): string[] =>
  files
    .filter((f) => f !== FONT_STYLESHEET)
    .flatMap((f) =>
      // COMMENTS FIRST, and this is not a nicety: index.css and tokens.css both DISCUSS the
      // @font-face in prose, and the first version of this guard reported all three of them.
      // A guard that fires on its own documentation is a guard that gets deleted.
      [...stripComments(read(f)).matchAll(/@font-face/gi)].map(
        () =>
          `${f} declares an @font-face. ${FONT_STYLESHEET} is the only file that may: UX-DR2 ` +
          `allows exactly one typeface, and a second @font-face introduces one without ` +
          `consuming a single banned value. Add the subset to ${FONT_STYLESHEET} instead.`,
      ),
    )

describe('exactly one typeface (AC 11, AC 11b, UX-DR2)', () => {
  const shippedStylesheets = git('ls-files', '*.css')
    .split('\n')
    .filter(Boolean)
    .filter((f) => !f.startsWith('tests/fixtures/'))

  it('is reading real stylesheets', () => {
    // Non-vacuity: the ban below filters this list, and an empty one passes it silently.
    expect(shippedStylesheets).toContain(FONT_STYLESHEET)
    expect(shippedStylesheets).toContain('src/styles/tokens.css')
    expect(shippedStylesheets.length).toBeGreaterThan(2)
  })

  it('declares @font-face in the font stylesheet and nowhere else', () => {
    expect(
      findStrayFontFaces(shippedStylesheets, (f) => readFileSync(join(uiRoot, f), 'utf8')),
    ).toEqual([])
    // …and the font stylesheet really does carry one, so the ban is not passing because
    // nothing anywhere declares a face.
    expect(readFileSync(join(uiRoot, FONT_STYLESHEET), 'utf8')).toContain('@font-face')
  })

  it('catches a second @font-face wherever it is hidden (the firing half)', () => {
    const planted = findStrayFontFaces(
      ['src/components/Panel.css'],
      () =>
        `.panel { color: var(--text-primary); }
       @font-face { font-family: 'Comic Sans MS'; src: url('./comic.woff2') format('woff2'); }`,
    )
    expect(planted).toHaveLength(1)
    expect(planted[0]).toContain('only file that may')
    expect(planted[0]).toContain(FONT_STYLESHEET)

    // Case is an evasion of its own, and CSS at-rule names are case-insensitive.
    expect(findStrayFontFaces(['src/x.css'], () => '@FONT-FACE { font-family: x; }')).toHaveLength(
      1,
    )
  })

  it('proves the role tokens hold only weights 400, 500 and 700 (AC 11)', () => {
    // AC 11 asks that no text on a dark surface falls below weight 400. That is a CONSEQUENCE
    // of the literal ban rather than a rule of its own: the only legal way to set type is the
    // seven role tokens, so their weights ARE the set of weights the application can produce.
    // Asserting them is what turns that argument into a proof — and it is the assertion that
    // fails if a later story adds a 300-weight role token to "soften" a caption.
    const tokens = readFileSync(join(uiRoot, 'src/styles/tokens.css'), 'utf8')
    const roleWeights = [...tokens.matchAll(/--type-([a-z-]+):\s*(\d{3})\s/g)].map((m) => ({
      role: m[1],
      weight: Number(m[2]),
    }))
    expect(roleWeights).toHaveLength(7)
    for (const { role, weight } of roleWeights) {
      expect(weight, `--type-${role} is below the 400 floor (UX-DR2)`).toBeGreaterThanOrEqual(400)
    }
    expect(new Set(roleWeights.map((r) => r.weight))).toEqual(new Set([400, 500, 700]))
    // …and all three are inside the @font-face's declared axis, or the browser synthesises.
    const axis = /font-weight:\s*(\d+)\s+(\d+)/.exec(
      readFileSync(join(uiRoot, FONT_STYLESHEET), 'utf8'),
    )
    expect(axis).not.toBeNull()
    for (const { weight } of roleWeights) {
      expect(weight).toBeGreaterThanOrEqual(Number(axis![1]))
      expect(weight).toBeLessThanOrEqual(Number(axis![2]))
    }
  })
})

// ---------------------------------------------------------------------------------------
// AC 5 — nothing in the shipped bundle reaches another host
// ---------------------------------------------------------------------------------------

/**
 * THE PROBLEM THIS GUARD HAD TO SOLVE, MEASURED BEFORE IT WAS WRITTEN.
 *
 * "Fail on any http:// in the bundle" is the obvious rule and it is RED on a clean build:
 * React's DOM code carries `http://www.w3.org/2000/svg` (a namespace IDENTIFIER passed to
 * createElementNS — never fetched) and `https://react.dev/errors/` (a string concatenated into
 * an error message). The favicon carries an SVG xmlns for the same reason. A guard that fires
 * on those is a guard someone switches off.
 *
 * So the rule is split by what the file type can actually DO, and each half is total within
 * its own domain rather than allow-listed:
 *
 *   R1  .css and .html — NO external URL of any kind. These are the two file types where a
 *       font CDN reference can live (`@import url(https://fonts.googleapis.com/…)`,
 *       `<link href="https://fonts.gstatic.com/…">`), they are emitted by the bundler from
 *       sources this repo owns, and measured on the real bundle they contain none. Total ban,
 *       no exceptions, which is AC 5's literal wording holding exactly where it can.
 *   R2  every file — no reference to a WEB-FONT CDN, matched as a family (any host whose name
 *       contains `font`, plus typekit), with the two Google hosts named by AC 5 asserted
 *       explicitly. Named hosts alone would be an enumeration a fifth CDN walks around.
 *   R3  every file — no external URL naming a FETCHABLE ASSET (.woff2/.woff/.ttf/.otf/.eot/
 *       .css/.js/.mjs). Keyed on the extension family rather than the host, so a CDN nobody
 *       has heard of is caught by what it serves.
 *   R4  every file — the SET of external hosts present equals a reviewed baseline. This is the
 *       one that catches what R1-R3 cannot imagine: a dependency that starts phoning home goes
 *       red and a human looks. It is deliberately brittle. Under AD-13 the bundle is committed,
 *       so a dependency bump already means committing a new bundle; this makes the new hosts
 *       part of that same review rather than a silent diff in a minified line.
 *
 * WHAT IS STILL NOT COVERED, said in the same breath: a runtime-constructed URL
 * (`fetch('htt' + 'ps://…')`) is invisible to all four, as it is to every static check. That is
 * not what this AC is about — the thing being prevented is the design system's CDN font import,
 * which is a build-time, statically visible construct in CSS or HTML, and R1 is absolute there.
 */

/** Hosts the reviewed bundle contains, and why each is not a fetch. */
const REVIEWED_HOSTS = new Set([
  'www.w3.org', // XML/SVG/MathML namespace identifiers — arguments to createElementNS
  'react.dev', // the base of React's error-message links, concatenated into a string
])

const FONT_CDN =
  /(^|\.)(fonts?\.[a-z0-9-]+\.[a-z]{2,}|[a-z0-9-]*font[a-z0-9-]*\.[a-z]{2,}|use\.typekit\.net)$/i
const FETCHABLE_ASSET = /\.(woff2?|ttf|otf|eot|css|m?js)(\?|#|$)/i

/** Every `https://host/path`, `http://host/path` and protocol-relative `//host/path`. */
const externalReferences = (text: string): { url: string; host: string }[] =>
  [...text.matchAll(/(?:https?:)?\/\/([A-Za-z0-9._-]+)(\/[^\s"'`)<>\\]*)?/g)].map((m) => ({
    url: m[0],
    host: m[1].toLowerCase(),
  }))

const TOTAL_BAN_EXTENSIONS = ['.css', '.html']

interface BundleFile {
  path: string
  /** null for a binary member (the font itself) — AC 2 checks those by signature, not text. */
  text: string | null
}

const findExternalReferences = (files: { path: string; text: string }[]): string[] => {
  const findings: string[] = []
  for (const file of files) {
    for (const { url, host } of externalReferences(file.text)) {
      const where = `${file.path} references ${url}`
      const totalBan = TOTAL_BAN_EXTENSIONS.some((ext) => file.path.endsWith(ext))

      if (totalBan) {
        findings.push(
          `${where}. No .css or .html in the bundle may name another host at all (UX-DR2, ` +
            `NFR-06): the app renders identically with the network blocked, so every byte it ` +
            `needs is served from its own origin. Self-host the asset under ui/src/assets/.`,
        )
        continue
      }
      if (FONT_CDN.test(host)) {
        findings.push(
          `${where}, which is a web-font CDN. The typeface is self-hosted (UX-DR2) — see ` +
            `ui/src/styles/fonts.css.`,
        )
        continue
      }
      if (FETCHABLE_ASSET.test(url)) {
        findings.push(
          `${where}, which is a fetchable asset on another origin. Commit it under ` +
            `ui/src/assets/ and let the bundler hash it into assets/ (NFR-06).`,
        )
        continue
      }
      if (!REVIEWED_HOSTS.has(host)) {
        findings.push(
          `${where} — a host no reviewer has signed off. Every external host in the bundle is ` +
            `listed in REVIEWED_HOSTS in this file with the reason it is not a fetch. If this ` +
            `one really is inert (a namespace URI, a doc link in an error string), add it there ` +
            `with that reason; if it is a request, it breaks the offline guarantee.`,
        )
      }
    }
  }
  return findings
}

const readBundle = (root: string): BundleFile[] => {
  const out: BundleFile[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) {
        walk(full)
        continue
      }
      // Binary members are LISTED but not read as text: AC 2 checks those by signature, and
      // decoding 22 kB of Brotli-compressed font as utf8 would produce mojibake that the URL
      // regex could match by accident. Listing them still matters — the assertion that the
      // font reached assets/ at all is a NAME check, and an earlier version of this walk
      // dropped them entirely, which made that assertion fail for the right reason by luck.
      const path = relative(root, full).replace(/\\/g, '/')
      const isBinary = /\.(woff2?|ttf|otf|eot|png|jpe?g|gif|ico|webp|avif)$/i.test(entry)
      out.push({ path, text: isBinary ? null : readFileSync(full, 'utf8') })
    }
  }
  walk(root)
  return out
}

describe('the shipped bundle reaches no other origin (AC 4, AC 5, NFR-06)', () => {
  const bundleRoot = join(repoRoot, BUNDLE)
  const files = readBundle(bundleRoot)
  const names = files.map((f) => f.path)
  /** The scannable half: everything the URL guard actually reads. */
  const text = files.filter((f): f is { path: string; text: string } => f.text !== null)

  it('is reading a real, populated, built bundle', () => {
    // THE NON-VACUITY ANCHOR. Every assertion below filters these lists; an empty one — a wrong
    // cwd, an unbuilt tree, a walk that never recursed — passes all of them by finding nothing.
    expect(names).toContain('index.html')
    expect(names.some((n) => /^assets\/index-[A-Za-z0-9_-]+\.css$/.test(n))).toBe(true)
    expect(names.some((n) => /^assets\/index-[A-Za-z0-9_-]+\.js$/.test(n))).toBe(true)
    expect(files.length).toBeGreaterThan(3)
    // The binary members are listed but unread, and the text members are genuinely read —
    // if these two ever collapsed into one number, one of the two halves stopped happening.
    expect(text.length).toBeLessThan(files.length)
    expect(text.length).toBeGreaterThan(2)
    // …and the JS really does carry external URLs, so R4's "no unreviewed host" is answering
    // a question that was actually asked.
    expect(text.flatMap((f) => externalReferences(f.text)).length).toBeGreaterThan(0)
  })

  it('emits the font into assets/, hashed, so it is cached immutably and served same-origin', () => {
    // AC 1. `assets/` is not cosmetic: spa.py applies `public, max-age=31536000, immutable`
    // by checking whether the FIRST PATH SEGMENT is `assets`, and `no-cache` to everything
    // else. A font in ui/public/ lands at the bundle root, unhashed, and is revalidated on
    // every single page load.
    const fonts = names.filter((n) => n.endsWith('.woff2'))
    expect(fonts).toHaveLength(1)
    expect(fonts[0]).toMatch(/^assets\/space-grotesk-latin-wght-normal-[A-Za-z0-9_-]+\.woff2$/)

    // The emitted stylesheet points at that exact file, same-origin and root-relative.
    const css = text.find((f) => f.path.endsWith('.css'))!
    expect(css.text).toContain(`/${fonts[0]}`)
    expect(css.text).toContain('@font-face')

    // And the preload in index.html names the SAME hashed file (Q5). A preload whose href has
    // drifted from the @font-face's url is not a slow font — it is the file downloaded twice.
    const html = text.find((f) => f.path === 'index.html')!
    expect(html.text).toMatch(/rel="preload"/)
    expect(html.text).toContain(`/${fonts[0]}`)
    // `crossorigin` even same-origin: font fetches are always CORS-mode, and without it the
    // preload is a different request than the real one, so nothing is reused.
    expect(html.text).toMatch(/crossorigin/)
  })

  it('names no external host in any .css or .html, and no font CDN anywhere', () => {
    expect(findExternalReferences(text)).toEqual([])

    // AC 5 names the two Google hosts explicitly, so they are asserted explicitly — a
    // regression that re-introduced the design system's own @import must fail by name and not
    // only as "some unreviewed host".
    const everything = text.map((f) => f.text).join('\n')
    expect(everything).not.toContain('fonts.googleapis.com')
    expect(everything).not.toContain('fonts.gstatic.com')
  })

  it('catches the CDN import in every shape it takes (the firing half)', () => {
    // Planted in fixtures, never in the real bundle — a build artefact edited by a test is a
    // build artefact that fails the drift check for the rest of the session.
    const planted = findExternalReferences([
      {
        path: 'assets/index-abc123.css',
        text: "@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk');",
      },
      {
        path: 'index.html',
        text: '<link rel="stylesheet" href="https://fonts.gstatic.com/s/spacegrotesk.css" />',
      },
      // Protocol-relative — neither `http://` nor `https://`, and the spelling a
      // copy-paste from a CDN's own snippet very often uses.
      { path: 'assets/index-abc123.css', text: "@import url('//fonts.googleapis.com/css2');" },
      // A CDN nobody enumerated, serving a font: caught by WHAT IT SERVES, not by its name.
      { path: 'assets/index-abc123.js', text: 'loadFont("https://cdn.example.net/x.woff2")' },
      // A host that is neither a CDN nor an asset: caught by the reviewed-host baseline.
      { path: 'assets/index-abc123.js', text: 'fetch("https://telemetry.example.com/beacon")' },
    ])

    expect(planted).toHaveLength(5)
    expect(planted[0]).toContain('No .css or .html in the bundle may name another host')
    expect(planted[1]).toContain('No .css or .html in the bundle may name another host')
    expect(planted[2]).toContain('No .css or .html in the bundle may name another host')
    expect(planted[3]).toContain('fetchable asset on another origin')
    expect(planted[4]).toContain('no reviewer has signed off')

    // The font-CDN branch is reachable from a file type the total ban does not cover, which is
    // what proves R2 is doing work rather than being shadowed by R1 on every input.
    const inJs = findExternalReferences([
      { path: 'assets/index-abc123.js', text: 'import("https://fonts.googleapis.com/x")' },
    ])
    expect(inJs).toHaveLength(1)
    expect(inJs[0]).toContain('web-font CDN')
  })

  it('leaves the real bundle alone in the same invocation (the silent half)', () => {
    // The pair. The same function, the same call shape, over the real committed tree — which
    // contains w3.org namespace URIs and a react.dev error link and must stay silent on both.
    expect(findExternalReferences(text)).toEqual([])
    expect(text.flatMap((f) => externalReferences(f.text)).map((r) => r.host)).toContain(
      'www.w3.org',
    )
  })

  it('has a fixture pair on disk too, so the guard is exercised by files and not only strings', () => {
    const cdn = readFileSync(fixture('css/font-cdn-violation.css'), 'utf8')
    const clean = readFileSync(fixture('css/clean.css'), 'utf8')

    expect(
      findExternalReferences([{ path: 'assets/index-abc123.css', text: cdn }]).length,
    ).toBeGreaterThan(0)
    expect(findExternalReferences([{ path: 'assets/index-abc123.css', text: clean }])).toEqual([])
  })
})
