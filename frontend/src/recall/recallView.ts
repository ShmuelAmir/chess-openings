import type {
  Backend,
  DrillAttempt,
  GameFilters,
  RecallGap,
  RecallView,
  SyncResult,
} from "../backend/backend";
import type { SyncClient } from "../sync/syncClient";
import { errorMessage } from "../errorMessage";
import { loadFilters, saveFilters } from "./storedFilters";

/** Where the Drill Attempt of a finished drill is in being saved. */
export type SaveState = null | "saving" | "saved" | "failed";

/**
 * The drill on the board. `drillNumber` tells it from the drill before;
 * `saveState` is null until the drill is finished.
 */
export interface DrillProgress {
  drillNumber: number;
  saveState: SaveState;
}

/** A single drill of a Recall Gap, as the gap was when the drill started. */
export interface SingleDrill extends DrillProgress {
  kind: "drill";
  gap: RecallGap;
}

/**
 * A practice session: the due Recall Gaps in ranking order (`queue`, null
 * while it loads), the one being drilled (`index`), how many gaps have been
 * drilled, and why the queue failed to load, until it loads again.
 */
export interface PracticeSession extends DrillProgress {
  kind: "session";
  queue: RecallGap[] | null;
  index: number;
  drilled: number;
  error: string | null;
}

/** The practice in progress, as the recall view keeps it. */
export type Practice = SingleDrill | PracticeSession;

/**
 * A practice session as components see it: `gap` is the one to drill now, so
 * the queue has loaded; none while the queue loads, or once nothing is due.
 */
export type ShownSession =
  | (PracticeSession & { queue: RecallGap[]; gap: RecallGap })
  | (PracticeSession & { gap: undefined });

/** The practice as components see it. */
export type ShownPractice = SingleDrill | ShownSession;

interface RecallViewState {
  filters: GameFilters;
  /** The recall view as the backend reports it: studies, gaps and totals. */
  view: RecallView | null;
  loading: boolean;
  /** Why the last load failed, until the next one starts. */
  error: string | null;
  selectedKey: string | null;
  showClosed: boolean;
  /** Whether the Progress panel shows in place of the selected gap; never during practice. */
  progressOpen: boolean;
  practice: Practice | null;
  /**
   * The last Sync's result, for the "what changed" line: held during
   * practice with the analysis it describes.
   */
  syncResult: SyncResult | null;
}

/** What the recall page renders from: the state, and what follows from it. */
export interface RecallViewSnapshot extends Omit<
  RecallViewState,
  "selectedKey" | "practice"
> {
  practice: ShownPractice | null;
  shownGaps: RecallGap[];
  closedCount: number;
  /** The selected gap if it is still shown, else the first. */
  selected: RecallGap | undefined;
}

/** The recall view store; see `createRecallView`. */
export interface RecallViewStore {
  getSnapshot(): RecallViewSnapshot;
  /** Hear of each new snapshot; returns the unsubscribe. */
  subscribe(listener: () => void): () => void;
  /**
   * Change the Game Filters: remembered in the browser, and the view
   * reloads. Ignored during practice, when the Game Filters stay as they are.
   */
  setFilters(filters: GameFilters): void;
  /** Select the Recall Gap with this position key; ends a drill of another gap. */
  selectGap(positionKey: string): void;
  /** Open the Progress panel in place of the selected gap; not during practice. */
  openProgress(): void;
  closeProgress(): void;
  toggleClosed(): void;
  startDrill(): void;
  /**
   * Start a practice session: the due Open Recall Gaps among those the
   * Game Filters show, one drill after another.
   */
  startSession(): void;
  /**
   * Move the practice session on to its next Recall Gap, once the Drill
   * Attempt is saved. A queue that has run out is fetched again, so gaps
   * failed on the way come back; until it arrives there is no drill to
   * move on from.
   */
  nextDrill(): void;
  /** Load the practice session's queue again after it failed to load. */
  retryQueue(): void;
  /**
   * The drill on the board is finished: record its Drill Attempt, once
   * however often it is reported. Without a Recall Gap on the board there
   * is nothing to record.
   */
  finishDrill(finished: DrillAttempt): void;
  /** Save the Drill Attempt again after its save failed. */
  retrySave(): void;
  /** Start a new drill of the single drill's Recall Gap. */
  drillAgain(): void;
  /** End the practice, and apply what a Sync changed meanwhile. */
  endPractice(): void;
  dispose(): void;
}

/**
 * The recall view, for as long as the recall page is open: the ranked Recall
 * Gaps and totals under the Game Filters, which gap is selected, and the
 * practice in progress.
 *
 * `backend` is the backend adapter and `syncClient` the account's Sync
 * client; a Sync that changed something reloads the view. A Sync never
 * interrupts practice: its change, and its "what changed" line, are held
 * until practice ends. Read with `getSnapshot()`, and `subscribe(listener)`
 * to hear of each new snapshot. `dispose()` when the page closes; a disposed
 * recall view does nothing more.
 */
export function createRecallView({
  backend,
  syncClient,
}: {
  backend: Backend;
  syncClient: SyncClient;
}): RecallViewStore {
  let state: RecallViewState = {
    filters: loadFilters(),
    view: null,
    loading: false,
    error: null,
    selectedKey: null,
    showClosed: false,
    progressOpen: false,
    practice: null,
    syncResult: syncClient.getSnapshot().result,
  };
  let snapshot = derive(state);
  const listeners = new Set<() => void>();
  // Only the latest load may update the view
  let latestLoad = 0;
  // A load dropped or kept back during practice, to run when practice ends
  let loadOwed = false;
  // How many drills have started, to tell one drill from the next
  let drills = 0;
  // The Drill Attempt of the drill on the board, once it is finished
  let attempt: DrillAttempt | null = null;
  // Only the latest queue load may update the practice session
  let latestQueueLoad = 0;
  let disposed = false;

  function setState(changes: Partial<RecallViewState>) {
    state = { ...state, ...changes };
    snapshot = derive(state);
    listeners.forEach((listener) => listener());
  }

  async function load() {
    const request = ++latestLoad;
    const filters = state.filters;
    setState({ loading: true, error: null });
    try {
      const view = await backend.loadRecallView(filters);
      if (request !== latestLoad) return;
      // Forget selected studies that are no longer in the Repertoire (an
      // empty list says nothing about them, so keep the selection then)
      const known = new Set(view.studies.map((study) => study.id));
      if (known.size > 0 && filters.studies.some((id) => !known.has(id))) {
        changeFilters({
          ...filters,
          studies: filters.studies.filter((id) => known.has(id)),
        });
        return;
      }
      setState({ view, loading: false });
    } catch (err) {
      if (request === latestLoad)
        setState({ error: errorMessage(err), loading: false });
    }
  }

  function changeFilters(filters: GameFilters) {
    if (disposed) return;
    saveFilters(filters);
    // The load publishes the new filters with its own snapshot
    state = { ...state, filters };
    load();
  }

  // Only called during practice: the drill on the board moves on
  function setPractice(changes: Partial<DrillProgress>) {
    if (state.practice)
      setState({ practice: { ...state.practice, ...changes } });
  }

  // Only called during a practice session
  function setSession(changes: Partial<PracticeSession>) {
    if (state.practice?.kind === "session")
      setState({ practice: { ...state.practice, ...changes } });
  }

  // A drill that has yet to be played, and to record its Drill Attempt
  function newDrill(): DrillProgress {
    attempt = null;
    return { drillNumber: ++drills, saveState: null };
  }

  async function saveAttempt() {
    // Only called once the drill on the board is finished
    if (!state.practice || !attempt) return;
    const { drillNumber } = state.practice;
    // The answer is for this drill only: not the next one, nor after practice
    const current = () =>
      !disposed && state.practice?.drillNumber === drillNumber;
    setPractice({ saveState: "saving" });
    try {
      await backend.recordDrillAttempt(attempt);
      if (current()) setPractice({ saveState: "saved" });
    } catch {
      if (current()) setPractice({ saveState: "failed" });
    }
  }

  // The practice session's queue, under the Game Filters, which stay as they
  // are during practice; its first Recall Gap is the next drill. The session
  // has no queue meanwhile, so no gap to drill until the new one arrives
  async function loadQueue() {
    const request = ++latestQueueLoad;
    setSession({ queue: null, index: 0, error: null });
    try {
      const queue = await backend.loadPracticeQueue(state.filters);
      if (request === latestQueueLoad) setSession({ queue, ...newDrill() });
    } catch (err) {
      if (request === latestQueueLoad) setSession({ error: errorMessage(err) });
    }
  }

  // Practice begins: the view stays as it is until practice ends, so a load
  // under way is dropped
  function startPractice(
    practice:
      | Omit<SingleDrill, keyof DrillProgress>
      | Omit<PracticeSession, keyof DrillProgress>,
  ) {
    latestQueueLoad++;
    const changes: Partial<RecallViewState> = {
      practice: { ...practice, ...newDrill() },
      progressOpen: false,
    };
    if (state.loading) {
      latestLoad++;
      loadOwed = true;
      changes.loading = false;
    }
    // Keep the selected gap across the held analysis, if it still exists
    if (snapshot.selected) changes.selectedKey = snapshot.selected.position_key;
    setState(changes);
  }

  function endPractice() {
    if (disposed || !state.practice) return;
    latestQueueLoad++;
    setState({ practice: null, syncResult: syncClient.getSnapshot().result });
    if (loadOwed) {
      loadOwed = false;
      load();
    }
  }

  const stopListening = [
    syncClient.onChanged(() => {
      if (state.practice) loadOwed = true;
      else load();
    }),
    syncClient.subscribe(() => {
      const { result } = syncClient.getSnapshot();
      if (!state.practice && result !== state.syncResult)
        setState({ syncResult: result });
    }),
  ];

  load();

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setFilters(filters) {
      if (disposed || state.practice) return;
      changeFilters(filters);
    },
    selectGap(positionKey) {
      if (disposed) return;
      const { practice } = state;
      if (
        practice?.kind === "drill" &&
        positionKey !== practice.gap.position_key
      )
        endPractice();
      setState({ selectedKey: positionKey, progressOpen: false });
    },
    openProgress() {
      if (disposed || state.practice) return;
      setState({ progressOpen: true });
    },
    closeProgress() {
      if (disposed) return;
      setState({ progressOpen: false });
    },
    toggleClosed() {
      if (disposed) return;
      setState({ showClosed: !state.showClosed });
    },
    startDrill() {
      const { selected } = snapshot;
      if (disposed || !selected) return;
      startPractice({ kind: "drill", gap: selected });
    },
    startSession() {
      if (disposed) return;
      startPractice({
        kind: "session",
        queue: null,
        index: 0,
        drilled: 0,
        error: null,
      });
      loadQueue();
    },
    nextDrill() {
      const { practice } = state;
      if (disposed || practice?.kind !== "session" || !practice.queue) return;
      if (practice.saveState !== "saved") return;
      const drilled = practice.drilled + 1;
      if (practice.index + 1 < practice.queue.length) {
        setSession({ drilled, index: practice.index + 1, ...newDrill() });
      } else {
        setSession({ drilled });
        loadQueue();
      }
    },
    retryQueue() {
      if (
        disposed ||
        state.practice?.kind !== "session" ||
        !state.practice.error
      )
        return;
      loadQueue();
    },
    finishDrill(finished) {
      if (disposed || !snapshot.practice?.gap || attempt) return;
      attempt = finished;
      saveAttempt();
    },
    retrySave() {
      if (disposed || state.practice?.saveState !== "failed") return;
      saveAttempt();
    },
    drillAgain() {
      if (disposed || state.practice?.kind !== "drill") return;
      setPractice(newDrill());
    },
    endPractice,
    dispose() {
      disposed = true;
      latestLoad++;
      latestQueueLoad++;
      stopListening.forEach((stop) => stop());
      listeners.clear();
    },
  };
}

function shownSession(session: PracticeSession): ShownSession {
  const gap = session.queue?.[session.index];
  return session.queue && gap
    ? { ...session, queue: session.queue, gap }
    : { ...session, gap: undefined };
}

function derive({
  selectedKey,
  practice,
  ...state
}: RecallViewState): RecallViewSnapshot {
  const gaps = state.view?.gaps ?? [];
  const shownGaps = gaps.filter(
    (gap) => state.showClosed || gap.status === "open",
  );
  return {
    ...state,
    practice: practice?.kind === "session" ? shownSession(practice) : practice,
    shownGaps,
    closedCount: gaps.filter((gap) => gap.status === "closed").length,
    selected:
      shownGaps.find((gap) => gap.position_key === selectedKey) ?? shownGaps[0],
  };
}
