/** SAN moves as a numbered line: ["e4", "c5", "Nf3"] -> "1.e4 c5 2.Nf3". */
export function formatLine(moves) {
  return moves
    .map((san, i) => (i % 2 === 0 ? `${i / 2 + 1}.${san}` : san))
    .join(" ");
}

/** A Unix timestamp as a local YYYY-MM-DD date. */
export function formatDate(ts) {
  return new Date(ts * 1000).toLocaleDateString("en-CA");
}
