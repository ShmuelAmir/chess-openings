import { useState } from "react";
import { Chessboard } from "react-chessboard";
import DrillBoard from "./DrillBoard";
import { formatLine, formatDate, formatStatus } from "./format";

const BOARD_WIDTH = 306;

/**
 * The sticky detail pane of the selected Recall Gap. Remount it per gap
 * (key it by position key), so a drill never carries over to another gap.
 */
export default function GapDetail({ gap }) {
  const [drilling, setDrilling] = useState(false);

  return (
    <section className="rv-detail">
      {gap ? (
        <>
          {drilling ? (
            <DrillBoard
              gap={gap}
              boardWidth={BOARD_WIDTH}
              onClose={() => setDrilling(false)}
            />
          ) : (
            <>
              <Chessboard
                id="gap-detail"
                // A position key is a FEN without the move counters
                position={`${gap.position_key} 0 1`}
                boardOrientation={gap.color}
                boardWidth={BOARD_WIDTH}
                arePiecesDraggable={false}
              />
              <div className="rv-line big">{formatLine(gap.path)} …</div>
              <button className="rv-practice" onClick={() => setDrilling(true)}>
                Practice this position
              </button>
            </>
          )}
          <div className={`rv-status ${gap.status}`}>{formatStatus(gap)}</div>
          <div className="rv-compare">
            <div>
              <div className="rv-label">You played</div>
              {gap.wrong_moves.map((m) => (
                <div key={m.san} className="rv-move bad">
                  {m.san} <span className="rv-muted">×{m.count}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="rv-label">Book</div>
              {gap.book_moves.map((m) => (
                <div key={m} className="rv-move good">
                  {m}
                </div>
              ))}
            </div>
          </div>

          <div className="rv-label">Games</div>
          <ul className="rv-games">
            {gap.games.map((g) => (
              <li key={g.url}>
                <a href={g.url} target="_blank" rel="noreferrer">
                  {formatDate(g.date)}
                </a>
                <span className="rv-muted">
                  {" "}
                  · {g.time_class} · played {g.move_played}
                  {g.result && (
                    <>
                      {" "}
                      · <span className={`rv-result ${g.result}`}>{g.result}</span>
                    </>
                  )}
                </span>
              </li>
            ))}
          </ul>

          <div className="rv-studylinks">
            {gap.studies.map((s) => (
              <a key={s.id} href={s.url} target="_blank" rel="noreferrer">
                Open in study: {s.name} ↗
              </a>
            ))}
          </div>
        </>
      ) : (
        <p className="rv-muted">Select a Recall Gap</p>
      )}
    </section>
  );
}
