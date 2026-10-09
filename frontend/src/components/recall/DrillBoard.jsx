import { useState, useEffect } from "react";
import { Chessboard } from "react-chessboard";
import {
  startDrill,
  userTurn,
  drillFen,
  playOpponent,
  playUserMove,
  drillAttempt,
  drillPassed,
  drillLine,
  movesFrom,
} from "./drill";
import { formatLine } from "./format";

const OPPONENT_DELAY_MS = 400;
const SELECTED_STYLE = { background: "rgba(255, 255, 0, 0.4)" };
const TARGET_STYLE = {
  background: "radial-gradient(circle, rgba(0, 0, 0, 0.25) 22%, transparent 24%)",
};

/**
 * A Drill Attempt of one Recall Gap on an in-app board, oriented to the
 * user's color. Reports the Drill Attempt with `onFinished` when the drill is
 * done; `saveState` is how its save is going ("saving", "saved" or "failed").
 * In a practice session, `onNext` moves on once the attempt is saved; a
 * single drill can be drilled again with `onAgain`.
 */
export default function DrillBoard({
  gap,
  boardWidth,
  saveState,
  onFinished,
  onRetrySave,
  onClose,
  onNext,
  onAgain,
}) {
  const [drill, setDrill] = useState(() => startDrill(gap));
  // The square of the piece picked up by a click, waiting for its target
  const [selected, setSelected] = useState(null);

  const turn = userTurn(drill);

  // The app plays the opponent's moves
  useEffect(() => {
    if (turn || drill.done) return;
    const timer = setTimeout(() => setDrill(playOpponent), OPPONENT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [drill, turn]);

  useEffect(() => {
    if (drill.done) onFinished(drillAttempt(drill));
  }, [drill.done]);

  const tryMove = (move) => {
    setSelected(null);
    const next = playUserMove(drill, move);
    if (!next) return false;
    setDrill(next);
    return true;
  };

  const onPieceDrop = (from, to, piece) => {
    // A promotion arrives as the chosen piece, e.g. "wQ"
    const promotion = piece[1] === "P" ? undefined : piece[1].toLowerCase();
    return tryMove({ from, to, promotion });
  };

  // Click a piece, then its target square; a click promotes to a queen
  const targets = selected ? movesFrom(drill, selected) : [];
  const onSquareClick = (square, piece) => {
    const move = targets.find((m) => m.to === square);
    if (move) tryMove(move);
    else if (square !== selected && piece?.[0] === gap.color[0] && movesFrom(drill, square).length)
      setSelected(square);
    else setSelected(null);
  };
  const squareStyles = selected
    ? Object.fromEntries([
        [selected, SELECTED_STYLE],
        ...targets.map((m) => [m.to, TARGET_STYLE]),
      ])
    : {};

  const passed = drillPassed(drill);

  return (
    <div className="rv-drill">
      <Chessboard
        id="gap-drill"
        position={drillFen(drill)}
        boardOrientation={gap.color}
        boardWidth={boardWidth}
        onPieceDrop={onPieceDrop}
        onPieceDragBegin={() => setSelected(null)}
        onSquareClick={onSquareClick}
        customSquareStyles={squareStyles}
        isDraggablePiece={({ piece }) => Boolean(turn) && piece[0] === gap.color[0]}
      />
      <div className="rv-line big">{formatLine(drillLine(drill))}</div>

      {drill.done ? (
        <div className={`rv-drill-msg ${passed ? "good" : "bad"}`}>
          {passed ? "Passed — every move was book." : "Failed — this attempt missed a book move."}
          {saveState === "saving" && <span className="rv-muted"> Saving…</span>}
          {saveState === "failed" && (
            <span>
              {" "}
              Could not save the attempt.{" "}
              <button className="rv-link" onClick={onRetrySave}>
                Retry
              </button>
            </span>
          )}
        </div>
      ) : drill.wrongMove ? (
        <div className="rv-drill-msg bad">
          {drill.wrongMove} is not book, so this attempt failed. Play one of:{" "}
          <b>{turn.book_moves.join(", ")}</b>
        </div>
      ) : drill.alsoBook ? (
        <div className="rv-drill-msg good">
          {drill.alsoBook} is also book. Continuing with your game's line.
        </div>
      ) : (
        <div className="rv-drill-msg rv-muted">
          {turn
            ? drill.ply === drill.gapPly
              ? "This is the gap: find a book move."
              : "Your move: play a book move."
            : "Opponent to move…"}
        </div>
      )}

      <div className="rv-drill-actions">
        {drill.done && onNext && (
          <button onClick={onNext} disabled={saveState !== "saved"}>
            Next
          </button>
        )}
        {drill.done && !onNext && <button onClick={onAgain}>Drill again</button>}
        <button className="secondary" onClick={onClose}>
          {drill.done && !onNext ? "Close" : "Stop"}
        </button>
      </div>
    </div>
  );
}
