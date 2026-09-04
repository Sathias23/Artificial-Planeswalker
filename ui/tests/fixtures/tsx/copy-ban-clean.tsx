/**
 * The silent half of the copy-ban pair: everything here is legal and looks like the thing the
 * ban is about. `!` as a non-null assertion and as a logical operator is never a string node;
 * a `//` comment with an exclamation mark is not a node at all — see below! And the header of
 * this file quotes the banned phrase "something went wrong" inside a comment, which is prose.
 */

interface Card {
  name?: string
}

export const CardName = ({ card }: { card: Card | null }) => {
  // The card is guaranteed present by the caller — assert it, do not check it!
  const name = card!.name
  const missing = !name
  return <p>{missing ? 'No name' : name}</p>
}

export const Calm = () => <p>Deck saved.</p>
