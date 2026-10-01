import { formatLine, formatDate } from "./format";

/** The ranked Recall Gaps, with the list header and totals strip. */
export default function GapList({ gaps, totals, selectedKey, onSelect, loading }) {
  return (
    <>
      <div className="rv-listhead">
        <strong>
          {gaps.length} Recall {gaps.length === 1 ? "Gap" : "Gaps"}
        </strong>
        <span className="rv-muted">
          {totals.analysed} games analysed · opponent left book{" "}
          {totals.opponent_left_book} · book completed {totals.book_completed}
          {loading && " · updating…"}
        </span>
      </div>

      {gaps.length === 0 && (
        <div className="empty-state">
          <p>No Recall Gaps for these filters</p>
        </div>
      )}

      {gaps.map((gap, i) => (
        <button
          key={gap.position_key}
          type="button"
          className={gap.position_key === selectedKey ? "rv-row active" : "rv-row"}
          onClick={() => onSelect(gap.position_key)}
        >
          <span className="rv-rank">{i + 1}</span>
          <span className="rv-main">
            <span className="rv-title">
              {gap.studies.map((s) => s.name).join(", ")}
              <span className={`rv-dot ${gap.color}`} />
            </span>
            <span className="rv-line">{formatLine(gap.path)}</span>
            <span className="rv-moves">
              you: {gap.wrong_moves.map((m) => `${m.san}×${m.count}`).join(", ")}{" "}
              · book: {gap.book_moves.join(" / ")}
            </span>
          </span>
          <span className="rv-count">
            <b>{gap.occurrences}×</b>
            <span className="rv-muted">{formatDate(gap.last_seen)}</span>
          </span>
        </button>
      ))}
    </>
  );
}
