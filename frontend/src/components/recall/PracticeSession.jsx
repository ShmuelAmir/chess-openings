import { useState, useEffect, useCallback } from "react";
import DrillBoard from "./DrillBoard";

const BOARD_WIDTH = 306;

/**
 * A practice session: drills the due Open Recall Gaps one after another, in
 * ranking order, until nothing is due or the user stops. Once the queue is
 * done it asks for it again, so gaps failed on the way come back.
 */
export default function PracticeSession({ fetchQueue: fetchQueueNow, onEnd }) {
  // The session keeps the Game Filters it started with
  const [fetchQueue] = useState(() => fetchQueueNow);
  const [queue, setQueue] = useState(null);
  const [index, setIndex] = useState(0);
  const [round, setRound] = useState(0);
  const [drilled, setDrilled] = useState(0);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setQueue(await fetchQueue());
      setIndex(0);
      setRound((r) => r + 1);
    } catch (err) {
      setError(err.message);
    }
  }, [fetchQueue]);

  useEffect(() => {
    load();
  }, []);

  const next = () => {
    setDrilled((n) => n + 1);
    if (index + 1 < queue.length) setIndex(index + 1);
    else load();
  };

  const gap = queue?.[index];

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
            <button onClick={load}>Retry</button>
            <button className="secondary" onClick={onEnd}>
              Stop
            </button>
          </div>
        </>
      ) : !queue ? (
        <p className="rv-muted">Loading the due Recall Gaps…</p>
      ) : gap ? (
        <DrillBoard
          key={`${round}-${index}`}
          gap={gap}
          boardWidth={BOARD_WIDTH}
          onNext={next}
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
