import { formatLine, formatDate, formatStatus } from "./format";

/** The ranked Recall Gaps, with the list header and totals strip. */
export default function GapList({
  gaps,
  closedCount,
  showClosed,
  onToggleClosed,
  totals,
  selectedKey,
  onSelect,
  loading,
  syncing,
}) {
  const openCount = gaps.filter((gap) => gap.status === "open").length;
  return (
    <>
      <div className="rv-listhead">
        <span className="rv-listtitle">
          <strong>
            {openCount} open Recall {openCount === 1 ? "Gap" : "Gaps"}
          </strong>
          {closedCount > 0 && (
            <label className="rv-switch">
              <input type="checkbox" checked={showClosed} onChange={onToggleClosed} />
              <span className="rv-switch-track" />
              Show closed ({closedCount})
            </label>
          )}
        </span>
        <span className="rv-muted">
          {totals.analysed} games analysed · opponent left book{" "}
          {totals.opponent_left_book} · book completed {totals.book_completed}
          {syncing ? " · Syncing…" : loading && " · updating…"}
        </span>
      </div>

      {gaps.length === 0 && (
        <div className="empty-state">
          <p>
            {closedCount > 0
              ? "Every Recall Gap for these filters is closed"
              : "No Recall Gaps for these filters"}
          </p>
        </div>
      )}

      {gaps.map((gap, i) => (
        <button
          key={gap.position_key}
          type="button"
          className={[
            "rv-row",
            gap.position_key === selectedKey && "active",
            gap.status === "closed" && "closed",
          ]
            .filter(Boolean)
            .join(" ")}
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
            <span className="rv-muted">{formatStatus(gap)}</span>
          </span>
        </button>
      ))}
    </>
  );
}
