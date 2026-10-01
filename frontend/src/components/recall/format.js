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

/** A Unix timestamp as how long ago it was: "just now", "12 min ago", "3 h ago". */
export function formatAgo(ts) {
  const minutes = Math.floor((Date.now() / 1000 - ts) / 60);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`;
  return `on ${formatDate(ts)}`;
}

/** A Recall Gap's status: its progress toward closing, or when it closed. */
export function formatStatus(gap) {
  return gap.status === "closed"
    ? `Closed ${formatDate(gap.closed_at)}`
    : `${gap.progress}/${gap.games_to_close} since last miss`;
}
