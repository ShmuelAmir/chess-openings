// The frontend backend seam: the calls the recall view store and the sync
// client make, and the domain types they take and return. Both adapters
// (httpBackend, memoryBackend) implement `Backend`. The types describe the
// API's JSON as it is today, field names included; nothing checks a response
// at runtime. A change to the API's shape updates these types and the API
// contract test in the same PR (coding standard 4).

/** A time control, as the Game Filters name it. */
export type TimeClass = "bullet" | "blitz" | "rapid" | "daily";

/** The Recall view's date-range presets. */
export type DateRange = "month" | "3months" | "year" | "all";

/** The Recall view's Game Filters. `studies` empty means all Studies. */
export interface GameFilters {
  timeClasses: TimeClass[];
  dateRange: DateRange;
  ratedOnly: boolean;
  studies: string[];
}

/** One source of a Sync (Chess.com or Lichess), as its last Sync left it. */
export interface SyncSourceStatus {
  status: "never" | "ok" | "failed";
  error: string | null;
  last_success_at: number | null;
}

/** What the account's last Sync changed. */
export interface SyncResult {
  games_changed: boolean;
  repertoire_changed: boolean;
  new_games: number;
  new_gaps: number;
  closed_gaps: number;
  reopened_gaps: number;
}

/** The account's Sync, as GET and POST /api/sync report it. */
export interface SyncState {
  running: boolean;
  progress: string | null;
  sources: { chess_com: SyncSourceStatus; lichess: SyncSourceStatus };
  /** The older source's last success; null if either never synced. */
  last_synced_at: number | null;
  runs: number;
  cached_games: number;
  /** null until a Sync has run for the account in this server process. */
  result: SyncResult | null;
}

/** A wrong move played at a Recall Gap, and how often. */
export interface WrongMove {
  san: string;
  count: number;
}

/** A game with an occurrence of a Recall Gap. */
export interface GapGame {
  url: string;
  date: number;
  time_class: string;
  move_played: string;
  /** The user's result; "" when unknown. */
  result: "win" | "loss" | "draw" | "";
}

/** A Study containing a Recall Gap's position, linked at that position. */
export interface GapStudy {
  id: string;
  name: string;
  url: string;
}

/** One of the user's turns on the way to a Recall Gap, as a drill plays it. */
export interface DrillTurn {
  /** Half-moves played before it. */
  ply: number;
  position_key: string;
  book_moves: string[];
}

/** A Recall Gap's status: Open with its progress toward closing, or Closed and when. */
export type RecallGapStatus = { progress: number; games_to_close: number } & (
  { status: "open"; closed_at: null } | { status: "closed"; closed_at: number }
);

/** A Recall Gap, as the Recall view and the practice queue list it. */
export type RecallGap = RecallGapStatus & {
  position_key: string;
  color: "white" | "black";
  /** SAN moves to the position in the most recent occurrence. */
  path: string[];
  wrong_moves: WrongMove[];
  book_moves: string[];
  studies: GapStudy[];
  occurrences: number;
  last_seen: number;
  /** Most recent first. */
  games: GapGame[];
  drill_turns: DrillTurn[];
};

/** One month of the Miss Rate and Miss Depth trend. */
export interface TrendMonth {
  /** "YYYY-MM", in UTC. */
  month: string;
  games: number;
  miss_rate: number | null;
  /** Misses by Miss Depth: the 2nd move first, the last counting every later move too. */
  miss_depths: number[];
  median_miss_depth: number | null;
}

/** The Recall view's totals under the Game Filters. */
export interface RecallTotals {
  analysed: number;
  opponent_left_book: number;
  book_completed: number;
  miss_rate: number | null;
  /** The last 12 months, oldest first, under every Game Filter but the date range. */
  trend: TrendMonth[];
  open_gaps: number;
  closed_in_range: number;
}

/** A Study of the Repertoire, as the Study filter lists it. */
export interface Study {
  id: string;
  name: string;
  opening_name: string;
  color: "white" | "black";
  /** Its Recall Gaps under every Game Filter but the Study filter. */
  gaps: number;
}

/** The Recall view, as GET /api/recall-view reports it. */
export interface RecallView {
  studies: Study[];
  gaps: RecallGap[];
  totals: RecallTotals;
}

/** A finished Drill Attempt: a pass, or a fail with its first miss's position. */
export interface DrillAttempt {
  gap_position_key: string;
  passed: boolean;
  first_miss_position_key: string | null;
}

/** The backend's answer to a recorded Drill Attempt. */
export interface DrillAttemptRecorded {
  recorded: true;
}

/**
 * The backend calls for one account. Each resolves with the call's result or
 * rejects with an Error whose message is fit to show the user.
 */
export interface Backend {
  readSyncState(): Promise<SyncState>;
  /** Start a Sync; resolves with the Sync state. */
  startSync(): Promise<SyncState>;
  loadRecallView(filters: GameFilters): Promise<RecallView>;
  /** The due Open Recall Gaps the Game Filters show, in ranking order. */
  loadPracticeQueue(filters: GameFilters): Promise<RecallGap[]>;
  recordDrillAttempt(attempt: DrillAttempt): Promise<DrillAttemptRecorded>;
}

/** The name of one of the Backend's calls. */
export type BackendCall = keyof Backend;

/** A FastAPI error body; empty when a failed response's body wasn't JSON. */
export interface ApiErrorBody {
  detail?: string;
}
