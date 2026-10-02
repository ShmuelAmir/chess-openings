import { Chess } from "chess.js";

/**
 * A Drill Attempt of one Recall Gap, as pure state. The drill replays the
 * gap's path from move 1: the app plays the opponent's moves, and at each of
 * the user's turns (`gap.drill_turns`) any book move is accepted. The first
 * wrong move fails the attempt there; the user must then play a book move to
 * continue. The drill ends when a book move is played at the gap.
 */
export function startDrill(gap) {
  return {
    gapPositionKey: gap.position_key,
    path: gap.path,
    turns: Object.fromEntries(gap.drill_turns.map((turn) => [turn.ply, turn])),
    gapPly: gap.path.length,
    ply: 0, // half-moves of the path played so far
    firstMiss: null, // the position key of the first wrong move
    wrongMove: null, // the wrong move just played, while its book moves are shown
    alsoBook: null, // a book move played that the line doesn't follow
    finalMove: null, // the book move played at the gap, which ends the drill
    done: false,
  };
}

/** The current turn the user must play, or null while it's the opponent's. */
export function userTurn(drill) {
  return drill.done ? null : (drill.turns[drill.ply] ?? null);
}

/** The board's FEN at the drill's current ply. */
export function drillFen(drill) {
  const chess = new Chess();
  drill.path.slice(0, drill.ply).forEach((san) => chess.move(san));
  if (drill.finalMove) chess.move(drill.finalMove);
  return chess.fen();
}

/** The app plays the opponent's next move of the path. */
export function playOpponent(drill) {
  if (userTurn(drill) || drill.done) return drill;
  return { ...drill, ply: drill.ply + 1 };
}

/**
 * The user tries a move, given as { from, to, promotion }. Returns the next
 * state, or null if the move is illegal (the piece snaps back).
 */
export function playUserMove(drill, move) {
  const turn = userTurn(drill);
  if (!turn) return null;

  const chess = new Chess(drillFen(drill));
  let san;
  try {
    san = chess.move(move).san;
  } catch {
    return null;
  }

  if (!turn.book_moves.includes(san)) {
    return {
      ...drill,
      firstMiss: drill.firstMiss ?? turn.position_key,
      wrongMove: san,
      alsoBook: null,
    };
  }

  const atGap = drill.ply === drill.gapPly;
  return {
    ...drill,
    // At the gap the drill ends on the move played; before it, the line goes on
    ply: atGap ? drill.ply : drill.ply + 1,
    wrongMove: null,
    alsoBook: !atGap && san !== drill.path[drill.ply] ? san : null,
    finalMove: atGap ? san : null,
    done: atGap,
  };
}

/** Whether the drill has had no wrong move so far. */
export function drillPassed(drill) {
  return drill.firstMiss === null;
}

/** The Drill Attempt to record once the drill is done. */
export function drillAttempt(drill) {
  return {
    gap_position_key: drill.gapPositionKey,
    passed: drillPassed(drill),
    first_miss_position_key: drill.firstMiss,
  };
}
