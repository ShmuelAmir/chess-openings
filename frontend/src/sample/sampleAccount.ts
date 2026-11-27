import { Chess } from "chess.js";
import type {
  Backend,
  DateRange,
  GameFilters,
  GapGame,
  RecallGap,
  RecallGapStatus,
  RecallView,
  Study,
  SyncSourceStatus,
  SyncState,
  TimeClass,
  TrendMonth,
} from "../backend/backend";
import { createMemoryBackend } from "../backend/memoryBackend";
import type { LichessUser } from "../context/AuthContext";

/*
 * The sample account: made-up Studies, Recall Gaps and a year of games,
 * answered by the in-memory backend so the real frontend runs without a
 * Lichess sign-in (`npm run dev:sample`). It follows the backend's rules
 * where the Recall page can see them (the Game Filters, ranking, the monthly
 * trend, the practice queue) without being the backend: Open / Closed and
 * when a gap is Due are fixed here, not worked out.
 *
 * Only `main.tsx` imports it, and only in the sample mode, so it never
 * reaches the production bundle. Importing its types elsewhere is fine:
 * `import type` is dropped from the build.
 */

/** The sample account: who it is signed in as, and the backend answering for it. */
export interface SampleAccount {
  lichessUser: LichessUser;
  chessComUsername: string;
  backend: Backend;
}

const DAY = 24 * 60 * 60;
// The backend's date range presets, in days back from now
const DATE_RANGE_DAYS: Record<DateRange, number | null> = {
  month: 30,
  "3months": 90,
  year: 365,
  all: null,
};
// The backend's rules for the totals and the trend
const GAMES_TO_CLOSE = 2;
const MIN_TREND_GAMES = 5;
const MIN_MEDIAN_MISSES = 3;
const FIRST_MISS_DEPTH = 2;
const LAST_MISS_DEPTH = 10;
const TREND_MONTHS = 12;
const TIME_CLASSES: TimeClass[] = [
  "blitz",
  "rapid",
  "blitz",
  "bullet",
  "rapid",
  "daily",
];
// How far back the sample games go: the trend's 12 months and a little more
const HISTORY_DAYS = 395;
// The latest move a sample miss comes on; the trend counts all from the 10th as one
const LATEST_MISS_DEPTH = 14;

const STUDIES: Omit<Study, "gaps">[] = [
  {
    id: "sItalian",
    name: "Italian Game - Giuoco Piano",
    opening_name: "Italian Game Giuoco Piano",
    color: "white",
  },
  {
    id: "sLondon",
    name: "London System",
    opening_name: "London System",
    color: "white",
  },
  {
    id: "sCaroKann",
    name: "Caro-Kann Defense",
    opening_name: "Caro Kann Defense",
    color: "black",
  },
  {
    id: "sNajdorf",
    name: "Sicilian Defense - Najdorf",
    opening_name: "Sicilian Defense Najdorf",
    color: "black",
  },
];

/*
 * The Recall Gaps. `line` reaches the gap's position, `bookMoves` are its
 * Book moves, `wrong` the moves played instead, one per occurrence, and
 * `seen` how many days ago each occurrence was. A closed gap
 * closed `closedDaysAgo`; `due` says whether a practice session drills it.
 */
type GapSpec = {
  studies: string[];
  line: string;
  bookMoves: string[];
  wrong: string[];
  seen: number[];
  due: boolean;
} & (
  | { status?: undefined; progress?: number }
  | { status: "closed"; closedDaysAgo: number }
);

const GAPS: GapSpec[] = [
  {
    studies: ["sItalian"],
    line: "e4 e5 Nf3 Nc6 Bc4 Bc5",
    bookMoves: ["c3", "d3"],
    wrong: ["O-O", "O-O", "Nc3", "O-O", "O-O", "Nc3"],
    seen: [2, 9, 15, 40, 120, 210],
    due: true,
  },
  {
    studies: ["sNajdorf"],
    line: "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3",
    bookMoves: ["a6"],
    wrong: ["e6", "Nc6", "e6", "g6", "e6"],
    seen: [1, 6, 22, 70, 150],
    due: true,
  },
  {
    studies: ["sCaroKann"],
    line: "e4 c6 d4 d5 e5",
    bookMoves: ["Bf5"],
    wrong: ["c5", "c5", "e6", "c5"],
    seen: [4, 12, 33, 95],
    due: false,
  },
  {
    studies: ["sLondon"],
    line: "d4 d5 Bf4 Nf6 e3 c5",
    bookMoves: ["c3"],
    wrong: ["Nf3", "dxc5", "Nf3", "Nf3"],
    seen: [3, 18, 50, 180],
    due: true,
  },
  {
    studies: ["sNajdorf"],
    line: "e4 c5 Nf3 d6 d4",
    bookMoves: ["cxd4"],
    wrong: ["Nf6", "Nf6", "e5"],
    seen: [8, 27, 200],
    due: true,
  },
  {
    studies: ["sItalian"],
    line: "e4 e5 Nf3 Nc6 Bc4 Nf6",
    bookMoves: ["d3"],
    wrong: ["Ng5", "Nc3", "Ng5"],
    seen: [55, 130, 240],
    status: "closed",
    closedDaysAgo: 20,
    due: false,
  },
  {
    studies: ["sCaroKann"],
    line: "e4 c6 d4 d5 Nc3 dxe4 Nxe4",
    bookMoves: ["Bf5"],
    wrong: ["Nf6", "Nd7"],
    seen: [10, 60],
    progress: 1,
    due: false,
  },
  {
    studies: ["sLondon"],
    line: "d4 d5 Bf4 Nf6 e3 e6",
    bookMoves: ["Nf3"],
    wrong: ["Bd3", "c4"],
    seen: [75, 160],
    status: "closed",
    closedDaysAgo: 45,
    due: false,
  },
  {
    studies: ["sNajdorf"],
    line: "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Bg5",
    bookMoves: ["e6"],
    wrong: ["Nbd7", "e5"],
    seen: [100, 190],
    status: "closed",
    closedDaysAgo: 80,
    due: false,
  },
  {
    studies: ["sCaroKann"],
    line: "e4 c6 d4 d5 exd5",
    bookMoves: ["cxd5"],
    wrong: ["Qxd5"],
    seen: [14],
    due: true,
  },
];

/** An occurrence of a gap: a game as the recall view lists it, and whether it was rated. */
type Occurrence = Omit<GapGame, "time_class"> & {
  time_class: TimeClass;
  rated: boolean;
};

/** `Omit` for each member of a union, so a Recall Gap keeps its status union. */
type DistributiveOmit<T, K extends PropertyKey> = T extends unknown
  ? Omit<T, K>
  : never;

/**
 * A Recall Gap as the backend would hold it: every occurrence, and whether it
 * is Due, but nothing worked out under the Game Filters yet.
 */
type SampleGap = DistributiveOmit<
  RecallGap,
  "wrong_moves" | "occurrences" | "last_seen" | "games"
> & { allGames: Occurrence[]; due: boolean };

/** How an analysed game left the book, and on which move if it was a miss. */
type Outcome =
  | { outcome: "miss"; depth: number }
  | {
      outcome: "in_book" | "opponent_left_book" | "book_completed";
      depth: null;
    };

/** An analysed game, with the Study its Deviation is in. */
type AnalysedGame = {
  date: number;
  time_class: TimeClass;
  rated: boolean;
  study: string;
} & Outcome;

type Miss = AnalysedGame & { outcome: "miss" };

/** A seeded random number generator, so the sample data is the same every time. */
function seededRandom(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A position's key: the FEN without its move counters, as the backend keys positions. */
const positionKey = (chess: Chess) =>
  chess.fen().split(" ").slice(0, 4).join(" ");

/** A date's UTC month, as "YYYY-MM". */
const isoMonth = (date: Date) => date.toISOString().slice(0, 7);

/** The UTC month of a Unix timestamp. */
const monthOf = (timestamp: number) => isoMonth(new Date(timestamp * 1000));

/** The month `back` months before the UTC month of `now`. */
function monthBefore(now: number, back: number) {
  const date = new Date(now * 1000);
  return isoMonth(
    new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - back, 1)),
  );
}

const RESULTS: GapGame["result"][] = ["loss", "win", "loss", "draw"];

const studyUrl = (id: string) => `https://lichess.org/study/${id}`;

/** Every Recall Gap with all its occurrences, as the backend would hold it. */
function buildGaps(now: number): SampleGap[] {
  return GAPS.map((spec, gapIndex) => {
    const path = spec.line.split(" ");
    const color = path.length % 2 === 0 ? "white" : "black";
    const chess = new Chess();
    const drillTurns: SampleGap["drill_turns"] = [];
    path.forEach((san, ply) => {
      if (ply % 2 === path.length % 2) {
        drillTurns.push({
          ply,
          position_key: positionKey(chess),
          book_moves: [san],
        });
      }
      chess.move(san);
    });
    const gapKey = positionKey(chess);
    drillTurns.push({
      ply: path.length,
      position_key: gapKey,
      book_moves: spec.bookMoves,
    });

    const games = spec.seen.map((daysAgo, i): Occurrence => ({
      url: `https://www.chess.com/game/live/${1000 + gapIndex * 20 + i}`,
      date: now - daysAgo * DAY - (gapIndex + 1) * 3600,
      time_class: TIME_CLASSES[(gapIndex + i) % TIME_CLASSES.length],
      rated: i % 5 !== 4,
      move_played: spec.wrong[i],
      result: RESULTS[(gapIndex + i) % RESULTS.length],
    }));

    const status: RecallGapStatus =
      spec.status === "closed"
        ? {
            status: "closed",
            progress: GAMES_TO_CLOSE,
            games_to_close: GAMES_TO_CLOSE,
            closed_at: now - spec.closedDaysAgo * DAY,
          }
        : {
            status: "open",
            progress: spec.progress ?? 0,
            games_to_close: GAMES_TO_CLOSE,
            closed_at: null,
          };
    return {
      position_key: gapKey,
      color,
      path,
      book_moves: spec.bookMoves,
      studies: spec.studies.map((id) => {
        const study = STUDIES.find((s) => s.id === id);
        if (!study) throw new Error(`No sample Study ${id}`);
        return { id, name: study.name, url: studyUrl(id) };
      }),
      ...status,
      drill_turns: drillTurns,
      allGames: games,
      due: spec.due,
    };
  });
}

/*
 * The analysed games: about 30 a month for 13 months, each with the Study its
 * Deviation is in. The Miss Rate falls and the misses come later in the line
 * over the year, so the Progress panel shows progress.
 */
function buildGames(now: number): AnalysedGame[] {
  const random = seededRandom(79);
  const games: AnalysedGame[] = [];
  for (let day = HISTORY_DAYS; day >= 0; day--) {
    const progress = 1 - day / HISTORY_DAYS; // 0 at the start, 1 today
    const perDay = random() < 0.5 ? 1 : 2;
    for (let i = 0; i < perDay; i++) {
      const roll = random();
      const missRate = 0.5 - 0.3 * progress;
      let outcome: Outcome = { outcome: "in_book", depth: null };
      if (roll < missRate) {
        const spread = 2 + Math.floor(random() * 5);
        const depth = Math.round(2 + 4 * progress + spread * (random() - 0.3));
        outcome = {
          outcome: "miss",
          depth: Math.min(Math.max(depth, FIRST_MISS_DEPTH), LATEST_MISS_DEPTH),
        };
      } else if (roll < missRate + 0.25) {
        outcome = { outcome: "opponent_left_book", depth: null };
      } else if (roll < missRate + 0.35) {
        outcome = { outcome: "book_completed", depth: null };
      }
      games.push({
        date: now - day * DAY - Math.floor(random() * DAY * 0.9),
        time_class: TIME_CLASSES[Math.floor(random() * TIME_CLASSES.length)],
        rated: random() < 0.85,
        study: STUDIES[Math.floor(random() * STUDIES.length)].id,
        ...outcome,
      });
    }
  }
  return games;
}

/** Whether a game, or a gap's occurrence, is inside every Game Filter but the Study filter. */
function inFilters(
  game: { time_class: TimeClass; rated: boolean; date: number },
  filters: GameFilters,
  since: number | null,
) {
  if (
    filters.timeClasses.length > 0 &&
    !filters.timeClasses.includes(game.time_class)
  )
    return false;
  if (filters.ratedOnly && !game.rated) return false;
  return since === null || game.date >= since;
}

const inStudies = (filters: GameFilters, ids: string[]) =>
  filters.studies.length === 0 ||
  ids.some((id) => filters.studies.includes(id));

/** The month's median Miss Depth: the earlier middle one of an even count. */
function median(depths: number[]) {
  const sorted = [...depths].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) / 2)];
}

function trendMonth(month: string, games: AnalysedGame[]): TrendMonth {
  const depths = games
    .filter((game): game is Miss => game.outcome === "miss")
    .map((game) => game.depth);
  const missDepths = new Array(LAST_MISS_DEPTH - FIRST_MISS_DEPTH + 1).fill(0);
  depths.forEach(
    (depth) =>
      missDepths[Math.min(depth, LAST_MISS_DEPTH) - FIRST_MISS_DEPTH]++,
  );
  return {
    month,
    games: games.length,
    miss_rate:
      games.length >= MIN_TREND_GAMES ? depths.length / games.length : null,
    miss_depths: missDepths,
    median_miss_depth:
      depths.length >= MIN_MEDIAN_MISSES ? median(depths) : null,
  };
}

/** A gap as the recall view shows it under the Game Filters, or null if no occurrence is inside them. */
function shownGap(
  { allGames, due, ...gap }: SampleGap,
  filters: GameFilters,
  since: number | null,
): RecallGap | null {
  const games = allGames
    .filter((game) => inFilters(game, filters, since))
    .sort((a, b) => b.date - a.date);
  if (games.length === 0) return null;
  const counts = new Map<string, number>();
  games.forEach((game) =>
    counts.set(game.move_played, (counts.get(game.move_played) ?? 0) + 1),
  );
  return {
    ...gap,
    wrong_moves: [...counts]
      .map(([san, count]) => ({ san, count }))
      .sort((a, b) => b.count - a.count),
    occurrences: games.length,
    last_seen: games[0].date,
    games: games.map(({ rated, ...game }) => game),
  };
}

const byRanking = (a: RecallGap, b: RecallGap) =>
  b.occurrences - a.occurrences || b.last_seen - a.last_seen;

/**
 * The sample account: a Lichess user and Chess.com username to show, and the
 * in-memory backend answering for them.
 */
export function createSampleAccount(): SampleAccount {
  const now = Math.floor(Date.now() / 1000);
  const gaps = buildGaps(now);
  const games = buildGames(now);
  const due = new Set(
    gaps.filter((gap) => gap.due).map((gap) => gap.position_key),
  );
  let runs = 0;

  const sinceOf = (filters: GameFilters) => {
    const days = DATE_RANGE_DAYS[filters.dateRange];
    return days === undefined || days === null ? null : now - days * DAY;
  };

  function recallView(filters: GameFilters): RecallView {
    const since = sinceOf(filters);
    // The gaps under every Game Filter but the Study filter, ranked
    const unfiltered = gaps
      .map((gap) => shownGap(gap, filters, since))
      .filter((gap) => gap !== null)
      .sort(byRanking);
    const shown = unfiltered.filter((gap) =>
      inStudies(
        filters,
        gap.studies.map((s) => s.id),
      ),
    );
    const studyGames = games.filter((game) => inStudies(filters, [game.study]));
    const counted = studyGames.filter((game) =>
      inFilters(game, filters, since),
    );
    const count = (outcome: AnalysedGame["outcome"]) =>
      counted.filter((game) => game.outcome === outcome).length;
    // The trend ignores the date range
    const trendGames = studyGames.filter((game) =>
      inFilters(game, filters, null),
    );
    const trend = Array.from({ length: TREND_MONTHS }, (_, i) => {
      const month = monthBefore(now, TREND_MONTHS - 1 - i);
      return trendMonth(
        month,
        trendGames.filter((game) => monthOf(game.date) === month),
      );
    });

    return {
      studies: [...STUDIES]
        .sort((a, b) => a.opening_name.localeCompare(b.opening_name))
        .map((study) => ({
          ...study,
          gaps: unfiltered.filter((gap) =>
            gap.studies.some((s) => s.id === study.id),
          ).length,
        })),
      gaps: shown,
      totals: {
        analysed: counted.length,
        opponent_left_book: count("opponent_left_book"),
        book_completed: count("book_completed"),
        miss_rate: counted.length ? count("miss") / counted.length : null,
        trend,
        open_gaps: shown.filter((gap) => gap.status === "open").length,
        closed_in_range: shown.filter(
          (gap) =>
            gap.status === "closed" &&
            (since === null || gap.closed_at >= since),
        ).length,
      },
    };
  }

  const syncState = (): SyncState => {
    const lastSync: SyncSourceStatus = {
      status: "ok",
      error: null,
      last_success_at: now - 5 * 60,
    };
    return {
      running: false,
      progress: null,
      sources: { chess_com: lastSync, lichess: lastSync },
      last_synced_at: lastSync.last_success_at,
      runs,
      cached_games: games.length,
      result:
        runs === 0
          ? null
          : {
              games_changed: false,
              repertoire_changed: false,
              new_games: 0,
              new_gaps: 0,
              closed_gaps: 0,
              reopened_gaps: 0,
            },
    };
  };

  const backend = createMemoryBackend();
  backend.on("readSyncState").reply(syncState);
  backend.on("startSync").reply(() => {
    runs++;
    return syncState();
  });
  backend.on("loadRecallView").reply(recallView);
  backend
    .on("loadPracticeQueue")
    .reply((filters) =>
      recallView(filters).gaps.filter(
        (gap) => gap.status === "open" && due.has(gap.position_key),
      ),
    );
  // A passed drill is not Due again in the sample; a failed one stays Due
  backend.on("recordDrillAttempt").reply((attempt) => {
    if (attempt.passed) due.delete(attempt.gap_position_key);
    return { recorded: true };
  });

  return {
    lichessUser: { id: "sample", username: "SampleUser" },
    chessComUsername: "sample-user",
    backend,
  };
}
