import DrillBoard from "./DrillBoard";

const BOARD_WIDTH = 306;

/**
 * A practice session: drills the due Open Recall Gaps one after another, in
 * ranking order, until nothing is due or the user stops. `session` is the
 * recall view's practice session.
 */
export default function PracticeSession({
  session,
  onFinished,
  onRetrySave,
  onNext,
  onRetryQueue,
  onEnd,
}) {
  const { queue, index, gap, drilled, error } = session;

  return (
    <section className="rv-detail">
      <div className="rv-session-head">
        <strong>Practice session</strong>
        {gap && (
          <span className="rv-muted">
            {" "}
            · {index + 1} of {queue.length} due
          </span>
        )}
      </div>

      {error ? (
        <>
          <div className="error">{error}</div>
          <div className="rv-drill-actions">
            <button onClick={onRetryQueue}>Retry</button>
            <button className="secondary" onClick={onEnd}>
              Stop
            </button>
          </div>
        </>
      ) : !queue ? (
        <p className="rv-muted">Loading the due Recall Gaps…</p>
      ) : gap ? (
        <DrillBoard
          key={session.drill}
          gap={gap}
          boardWidth={BOARD_WIDTH}
          saveState={session.save}
          onFinished={onFinished}
          onRetrySave={onRetrySave}
          onNext={onNext}
          onClose={onEnd}
        />
      ) : (
        <>
          <p className="rv-drill-msg good">
            Nothing is due.
            {drilled > 0 && ` You drilled ${drilled} ${drilled === 1 ? "gap" : "gaps"}.`}
          </p>
          <button className="secondary" onClick={onEnd}>
            Close
          </button>
        </>
      )}
    </section>
  );
}
