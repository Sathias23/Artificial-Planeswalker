/* FIXTURE — the acceptance half of the pair. Same lint invocation as violation.tsx.
   Without this file a passing test cannot tell "the a11y rules fired" from "the config
   errors on every file it touches". */

function noop() {}

export function InteractiveElement() {
  return (
    <button type="button" onClick={noop}>
      A real button
    </button>
  )
}

/* THE OTHER HALF OF c4-4's HANDLER NARROWING. `onLoad` and `onError` sit in jsx-a11y's DEFAULT
   handler list for both UX-DR47 rules, so before that change this element alone made the gate
   red — and it is the only way a component can know whether a card's picture arrived, which is
   the whole of the placeholder-then-fill contract. Here rather than described in a comment,
   because a narrowing that is not exercised by the clean fixture is a claim rather than a gate:
   if the handler list is ever restored to its default, THIS file goes red and the pair's
   silence assertion says which rule and which line. */
export function ImageWithLifecycleHandlers() {
  return <img src="/api/card-image/x" alt="" onLoad={noop} onError={noop} />
}
