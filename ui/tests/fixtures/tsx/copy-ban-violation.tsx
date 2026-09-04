/**
 * Three violations of UX-DR33's copy rules, one per ban, so `tests/lint-gates.test.ts` can
 * count exactly three `no-restricted-syntax` reports from this file: an exclamation mark in a
 * string literal, an emoji in a template chunk, and the banned phrase as JSX text.
 */

export const Done = () => <p>{'Done!'}</p>

export const Party = () => <p>{`Deck saved 🎉`}</p>

export const Shrug = () => <p>Something went wrong</p>
