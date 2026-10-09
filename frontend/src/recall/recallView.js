import { loadFilters, saveFilters } from "./storedFilters";

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
export function createRecallView({ backend, syncClient }) {
  let state = {
    filters: loadFilters(),
    // The recall view as the backend reports it: studies, gaps and totals
    view: null,
    loading: false,
    // Why the last load failed, until the next one starts
    error: null,
    selectedKey: null,
    showClosed: false,
    // The practice in progress: null, { kind: "drill", gap } with the gap as
    // it was when the drill started, or the practice session { kind:
    // "session", queue, index, drilled, error }. Both carry
    // `drillNumber`, which tells the drill on the board from the one before,
    // and `saveState`: null, then "saving", "saved" or "failed" once the
    // drill is finished
    practice: null,
    // The last Sync's result, for the "what changed" line: held during
    // practice with the analysis it describes
    syncResult: syncClient.getSnapshot().result,
  };
  let snapshot = derive(state);
  const listeners = new Set();
  // Only the latest load may update the view
  let latestLoad = 0;
  // A load dropped or kept back during practice, to run when practice ends
  let loadOwed = false;
  // How many drills have started, to tell one drill from the next
  let drills = 0;
  // The Drill Attempt of the drill on the board, once it is finished
  let attempt = null;
  // Only the latest queue load may update the practice session
  let latestQueueLoad = 0;
  let disposed = false;

  function setState(changes) {
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
        changeFilters({ ...filters, studies: filters.studies.filter((id) => known.has(id)) });
        return;
      }
      setState({ view, loading: false });
    } catch (err) {
      if (request === latestLoad) setState({ error: err.message, loading: false });
    }
  }

  function changeFilters(filters) {
    if (disposed) return;
    saveFilters(filters);
    // The load publishes the new filters with its own snapshot
    state = { ...state, filters };
    load();
  }

  function setPractice(changes) {
    setState({ practice: { ...state.practice, ...changes } });
  }

  // A drill that has yet to be played, and to record its Drill Attempt
  function newDrill() {
    attempt = null;
    return { drillNumber: ++drills, saveState: null };
  }

  async function saveAttempt() {
    const { drillNumber } = state.practice;
    // The answer is for this drill only: not the next one, nor after practice
    const current = () => !disposed && state.practice?.drillNumber === drillNumber;
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
    setPractice({ queue: null, index: 0, error: null });
    try {
      const queue = await backend.loadPracticeQueue(state.filters);
      if (request === latestQueueLoad) setPractice({ queue, ...newDrill() });
    } catch (err) {
      if (request === latestQueueLoad) setPractice({ error: err.message });
    }
  }

  // Practice begins: the view stays as it is until practice ends, so a load
  // under way is dropped
  function startPractice(practice) {
    latestQueueLoad++;
    const changes = { practice: { ...practice, ...newDrill() } };
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
      if (!state.practice && result !== state.syncResult) setState({ syncResult: result });
    }),
  ];

  load();

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    /**
     * Change the Game Filters: remembered in the browser, and the view
     * reloads. Ignored during practice, when the Game Filters stay as they are.
     */
    setFilters(filters) {
      if (disposed || state.practice) return;
      changeFilters(filters);
    },
    /** Select the Recall Gap with this position key; ends a drill of another gap. */
    selectGap(positionKey) {
      if (disposed) return;
      const { practice } = state;
      if (practice?.kind === "drill" && positionKey !== practice.gap.position_key) endPractice();
      setState({ selectedKey: positionKey });
    },
    /** Show or hide the Closed Recall Gaps. */
    toggleClosed() {
      if (disposed) return;
      setState({ showClosed: !state.showClosed });
    },
    /** Start a single drill of the selected Recall Gap. */
    startDrill() {
      if (disposed || !snapshot.selected) return;
      startPractice({ kind: "drill", gap: snapshot.selected });
    },
    /**
     * Start a practice session: the due Open Recall Gaps among those the
     * Game Filters show, one drill after another.
     */
    startSession() {
      if (disposed) return;
      startPractice({
        kind: "session",
        // The due Recall Gaps in ranking order; null while they are loaded
        queue: null,
        index: 0,
        // How many gaps the session has drilled
        drilled: 0,
        // Why the queue failed to load, until it is loaded again
        error: null,
      });
      loadQueue();
    },
    /**
     * Move the practice session on to its next Recall Gap, once the Drill
     * Attempt is saved. A queue that has run out is fetched again, so gaps
     * failed on the way come back; until it arrives there is no drill to
     * move on from.
     */
    nextDrill() {
      const { practice } = state;
      if (disposed || practice?.kind !== "session" || !practice.queue) return;
      if (practice.saveState !== "saved") return;
      const drilled = practice.drilled + 1;
      if (practice.index + 1 < practice.queue.length) {
        setPractice({ drilled, index: practice.index + 1, ...newDrill() });
      } else {
        setPractice({ drilled });
        loadQueue();
      }
    },
    /** Load the practice session's queue again after it failed to load. */
    retryQueue() {
      if (disposed || state.practice?.kind !== "session" || !state.practice.error) return;
      loadQueue();
    },
    /**
     * The drill on the board is finished: record its Drill Attempt, once
     * however often it is reported. Without a Recall Gap on the board there
     * is nothing to record.
     */
    finishDrill(finished) {
      if (disposed || !snapshot.practice?.gap || attempt) return;
      attempt = finished;
      saveAttempt();
    },
    /** Save the Drill Attempt again after its save failed. */
    retrySave() {
      if (disposed || state.practice?.saveState !== "failed") return;
      saveAttempt();
    },
    /** Start a new drill of the single drill's Recall Gap. */
    drillAgain() {
      if (disposed || state.practice?.kind !== "drill") return;
      setPractice(newDrill());
    },
    /** End the practice, and apply what a Sync changed meanwhile. */
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

// What the page renders from: the state, and what follows from it
function derive({ selectedKey, practice, ...state }) {
  const gaps = state.view?.gaps ?? [];
  const shownGaps = gaps.filter((gap) => state.showClosed || gap.status === "open");
  return {
    ...state,
    // A practice session's `gap` is the one to drill now; none while the
    // queue loads, or once nothing is due
    practice:
      practice?.kind === "session"
        ? { ...practice, gap: practice.queue?.[practice.index] }
        : practice,
    shownGaps,
    closedCount: gaps.filter((gap) => gap.status === "closed").length,
    // The selected gap if it is still shown, else the first
    selected: shownGaps.find((gap) => gap.position_key === selectedKey) ?? shownGaps[0],
  };
}
