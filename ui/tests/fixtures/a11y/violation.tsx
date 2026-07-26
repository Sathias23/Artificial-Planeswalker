/* FIXTURE — deliberately inaccessible. Not product code and not part of the app build.
   `npm run lint` ignores tests/fixtures/**; tests/lint-gates.test.ts lints this file
   through the ESLint Node API with ignores disabled and asserts both UX-DR47 rules fire.
   The handlers must sit on literal DOM elements: jsx-a11y cannot see a click handler on a
   component (`<Foo onClick={…}/>` is invisible to these rules). */

function noop() {}

export function StaticElementWithHandler() {
  return <div onClick={noop}>Looks clickable, is not a button</div>
}

export function NonInteractiveElementWithHandler() {
  return (
    <ul>
      <li onClick={noop}>Looks clickable, is a list item</li>
    </ul>
  )
}
