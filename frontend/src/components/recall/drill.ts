import { Chess, type PieceSymbol, type Square } from "chess.js";
import type { DrillAttempt, DrillTurn, RecallGap } from "../../backend/backend";

/** A drill under way; see `startDrill`. */
export interface DrillState {
  gapPositionKey: string;
  /** SAN moves to the gap's position. */
  path: string[];
  /** The user's turns, by the ply they come at. */
  turns: Record<number, DrillTurn>;
  gapPly: number;
  /** Half-moves of the path played so far. */
  ply: number;
  /** The position key of the first wrong move. */
  firstMiss: string | null;
  /** The wrong move just played, while its book moves are shown. */
  wrongMove: string | null;
  /** A book move played that the line doesn't follow. */
  alsoBook: string | null;
  /** The book move played at the gap, which ends the drill. */
  finalMove: string | null;
  done: boolean;
}

/** A move made on the board, from one square to another. */
export interface BoardMove {
  from: Square;
  to: Square;
  promotion?: PieceSymbol;
}

/**
 * A Drill Attempt of one Recall Gap, as pure state. The drill replays the
 * gap's path from move 1: the app plays the opponent's moves, and at each of
 * the user's turns (`gap.drill_turns`) any book move is accepted. The first
 * wrong move fails the attempt there; the user must then play a book move to
 * continue. The drill ends when a book move is played at the gap.
 */
export function startDrill(gap: RecallGap): DrillState {
  return {
    gapPositionKey: gap.position_key,
    path: gap.path,
    turns: Object.fromEntries(gap.drill_turns.map((turn) => [turn.ply, turn])),
    gapPly: gap.path.length,
    ply: 0,
    firstMiss: null,
    wrongMove: null,
    alsoBook: null,
    finalMove: null,
    done: false,
  };
}

/** The current turn the user must play, or null while it's the opponent's. */
export function userTurn(drill: DrillState): DrillTurn | null {
  return drill.done ? null : (drill.turns[drill.ply] ?? null);
}

/** The moves played so far, ending with the move played at the gap once done. */
export function drillLine(drill: DrillState): string[] {
  const line = drill.path.slice(0, drill.ply);
  return drill.finalMove ? [...line, drill.finalMove] : line;
}

/** The board's FEN at the drill's current ply. */
export function drillFen(drill: DrillState): string {
  const chess = new Chess();
  drillLine(drill).forEach((san) => chess.move(san));
  return chess.fen();
}

/** The app plays the opponent's next move of the path. */
export function playOpponent(drill: DrillState): DrillState {
  if (userTurn(drill) || drill.done) return drill;
  return { ...drill, ply: drill.ply + 1 };
}

/**
 * The user tries a move made on the board. Returns the next state, or null
 * if the move is illegal (the piece snaps back).
 */
export function playUserMove(
  drill: DrillState,
  move: BoardMove,
): DrillState | null {
  const turn = userTurn(drill);
  if (!turn) return null;

  const chess = new Chess(drillFen(drill));
  let san: string;
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
export function drillPassed(drill: DrillState): boolean {
  return drill.firstMiss === null;
}

/** The Drill Attempt to record once the drill is done. */
export function drillAttempt(drill: DrillState): DrillAttempt {
  return {
    gap_position_key: drill.gapPositionKey,
    passed: drillPassed(drill),
    first_miss_position_key: drill.firstMiss,
  };
}

/**
 * The moves the user's piece on `square` can make now, one per target square
 * (a promotion becomes a queen). Empty when it isn't the user's turn or the
 * square holds no piece of theirs.
 */
export function movesFrom(drill: DrillState, square: Square): BoardMove[] {
  if (!userTurn(drill)) return [];
  const chess = new Chess(drillFen(drill));
  const byTarget = new Map<Square, BoardMove>();
  for (const move of chess.moves({ square, verbose: true })) {
    if (!byTarget.has(move.to) || move.promotion === "q") {
      byTarget.set(move.to, {
        from: move.from,
        to: move.to,
        promotion: move.promotion,
      });
    }
  }
  return [...byTarget.values()];
}
