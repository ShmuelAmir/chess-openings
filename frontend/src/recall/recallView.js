import { loadFilters, saveFilters } from "./storedFilters";

/**
 * The recall view, for as long as the recall page is open: the ranked Recall
 * Gaps and totals under the Game Filters, and which gap is selected.
 *
 * `backend` is the backend adapter and `syncClient` the account's Sync
 * client; a Sync that changed something reloads the view. Read with
 * `getSnapshot()`, and `subscribe(listener)` to hear of each new snapshot.
 * `dispose()` when the page closes; a disposed recall view does nothing more.
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
  };
  let snapshot = derive(state);
  const listeners = new Set();
  // Only the latest load may update the view
  let latestLoad = 0;
  // While held (the page is practising) a Sync's change does not reload the
  // view; a load dropped or kept back is owed on release
  let held = false;
  let loadOwed = false;
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

  const stopListening = syncClient.onChanged(() => {
    if (held) loadOwed = true;
    else load();
  });

  load();

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    /** Change the Game Filters: remembered in the browser, and the view reloads. */
    setFilters: changeFilters,
    /** Select the Recall Gap with this position key. */
    selectGap(positionKey) {
      if (disposed) return;
      setState({ selectedKey: positionKey });
    },
    /** Show or hide the Closed Recall Gaps. */
    toggleClosed() {
      if (disposed) return;
      setState({ showClosed: !state.showClosed });
    },
    /**
     * Keep the view as it is while the page practises: a load under way is
     * dropped and a Sync's change kept back, until `release()`.
     */
    hold() {
      if (disposed) return;
      held = true;
      if (state.loading) {
        latestLoad++;
        loadOwed = true;
        setState({ loading: false });
      }
    },
    /** End the hold, and load now if a load is owed. */
    release() {
      held = false;
      if (loadOwed && !disposed) {
        loadOwed = false;
        load();
      }
    },
    dispose() {
      disposed = true;
      latestLoad++;
      stopListening();
      listeners.clear();
    },
  };
}

// What the page renders from: the state, and what follows from it
function derive({ selectedKey, ...state }) {
  const gaps = state.view?.gaps ?? [];
  const shownGaps = gaps.filter((gap) => state.showClosed || gap.status === "open");
  return {
    ...state,
    shownGaps,
    closedCount: gaps.filter((gap) => gap.status === "closed").length,
    // The selected gap if it is still shown, else the first
    selected: shownGaps.find((gap) => gap.position_key === selectedKey) ?? shownGaps[0],
  };
}
