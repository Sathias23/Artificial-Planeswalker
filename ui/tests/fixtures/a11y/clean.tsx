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
