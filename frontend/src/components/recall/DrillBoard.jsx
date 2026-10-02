import { useState, useEffect, useRef } from "react";
import { Chessboard } from "react-chessboard";
import {
  startDrill,
  userTurn,
  drillFen,
  playOpponent,
  playUserMove,
  drillAttempt,
  drillPassed,
} from "./drill";
import { formatLine } from "./format";

const OPPONENT_DELAY_MS = 400;

/**
 * A Drill Attempt of one Recall Gap on an in-app board, oriented to the
 * user's color. Records exactly one Drill Attempt when the drill is done.
 */
export default function DrillBoard({ gap, boardWidth, onClose }) {
  const [drill, setDrill] = useState(() => startDrill(gap));
  const [saveState, setSaveState] = useState(null); // "saving" | "saved" | "error"
  const recorded = useRef(false);

  const turn = userTurn(drill);

  // The app plays the opponent's moves
  useEffect(() => {
    if (turn || drill.done) return;
    const timer = setTimeout(() => setDrill(playOpponent), OPPONENT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [drill, turn]);

  const saveAttempt = async () => {
    setSaveState("saving");
    try {
      const response = await fetch("/api/drill-attempts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(drillAttempt(drill)),
      });
      if (!response.ok) throw new Error();
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  };

  useEffect(() => {
    if (!drill.done || recorded.current) return;
    recorded.current = true;
    saveAttempt();
  }, [drill.done]);

  const onPieceDrop = (from, to, piece) => {
    // A promotion arrives as the chosen piece, e.g. "wQ"
    const promotion = piece[1] === "P" ? undefined : piece[1].toLowerCase();
    const next = playUserMove(drill, { from, to, promotion });
    if (!next) return false;
    setDrill(next);
    return true;
  };

  const passed = drillPassed(drill);

  return (
    <div className="rv-drill">
      <Chessboard
        id="gap-drill"
        position={drillFen(drill)}
        boardOrientation={gap.color}
        boardWidth={boardWidth}
        onPieceDrop={onPieceDrop}
        isDraggablePiece={({ piece }) => Boolean(turn) && piece[0] === gap.color[0]}
      />
      <div className="rv-line big">{formatLine(drill.path.slice(0, drill.ply))}</div>

      {drill.done ? (
        <div className={`rv-drill-msg ${passed ? "good" : "bad"}`}>
          {passed ? "Passed — every move was book." : "Failed — this attempt missed a book move."}
          {saveState === "saving" && <span className="rv-muted"> Saving…</span>}
          {saveState === "error" && (
            <span>
              {" "}
              Could not save the attempt.{" "}
              <button className="rv-link" onClick={saveAttempt}>
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
        {drill.done && (
          <button
            onClick={() => {
              recorded.current = false;
              setSaveState(null);
              setDrill(startDrill(gap));
            }}
          >
            Drill again
          </button>
        )}
        <button className="secondary" onClick={onClose}>
          {drill.done ? "Close" : "Stop"}
        </button>
      </div>
    </div>
  );
}
