// Sync on open when the older source's last Sync is older than this
const SYNC_STALE_SECONDS = 10 * 60;
const SYNC_POLL_MS = 1000;

function isStale(lastSyncedAt) {
  return !lastSyncedAt || Date.now() / 1000 - lastSyncedAt > SYNC_STALE_SECONDS;
}

/**
 * The Sync client for one account, for as long as the app is open: it Syncs
 * on open when the last Sync is stale, polls a running Sync, and notices
 * each Sync that finishes.
 *
 * `backend` is the backend adapter. Read with `getSnapshot()`, and
 * `subscribe(listener)` to hear of each new snapshot. `onChanged(listener)`
 * announces a finished Sync that changed the games or the Repertoire.
 * `dispose()` when the account changes; a disposed client does nothing more.
 */
export function createSyncClient(backend) {
  let snapshot = {
    // The Sync state, as the backend reports it
    status: null,
    syncing: false,
    // Why the last request failed, until the next Sync state arrives
    error: null,
    // The result of the last Sync that finished since the app opened
    result: null,
  };
  const listeners = new Set();
  const changeListeners = new Set();
  let pollTimer = null;
  // How many Syncs had finished when we last looked, to notice a new result
  let seenRuns = null;
  let disposed = false;

  function setSnapshot(changes) {
    snapshot = { ...snapshot, ...changes };
    listeners.forEach((listener) => listener());
  }

  function applyStatus(status) {
    const changes = { status, syncing: Boolean(status.running), error: null };
    let finished = false;
    if (seenRuns === null) {
      seenRuns = status.runs;
    } else if (!status.running && status.runs > seenRuns) {
      seenRuns = status.runs;
      changes.result = status.result;
      finished = true;
    }
    setSnapshot(changes);
    schedulePoll(status.running);
    // Announce only a Sync that changed something
    const result = status.result;
    if (finished && result && (result.games_changed || result.repertoire_changed)) {
      changeListeners.forEach((listener) => listener());
    }
  }

  function schedulePoll(running) {
    // Poll the Sync's progress while it runs
    if (running && pollTimer === null) {
      pollTimer = setInterval(poll, SYNC_POLL_MS);
    } else if (!running && pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  // Ask the backend for the Sync state and apply it, or surface the failure.
  // Resolves with the state, or null if it failed or the client was disposed.
  async function request(call) {
    try {
      const status = await call();
      if (disposed) return null;
      applyStatus(status);
      return status;
    } catch (err) {
      if (!disposed) setSnapshot({ error: err.message });
      return null;
    }
  }

  const poll = () => request(backend.readSyncState);

  // On open: Sync if the older source's last Sync is stale
  (async () => {
    const status = await request(backend.readSyncState);
    if (status && !status.running && isStale(status.last_synced_at)) {
      await request(backend.startSync);
    }
  })();

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    onChanged(listener) {
      changeListeners.add(listener);
      return () => changeListeners.delete(listener);
    },
    /** Start a Sync now (the Sync button, or Retry). */
    async startSync() {
      if (disposed) return;
      setSnapshot({ error: null });
      await request(backend.startSync);
    },
    dispose() {
      disposed = true;
      schedulePoll(false);
      listeners.clear();
      changeListeners.clear();
    },
  };
}
