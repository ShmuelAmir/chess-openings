import type { Backend, SyncResult, SyncState } from "../backend/backend";

// Sync on open when the older source's last Sync is older than this
const SYNC_STALE_SECONDS = 10 * 60;
const SYNC_POLL_MS = 1000;

function isStale(lastSyncedAt: number | null): boolean {
  return !lastSyncedAt || Date.now() / 1000 - lastSyncedAt > SYNC_STALE_SECONDS;
}

/** What the Sync client reports: the Sync state and what follows from it. */
export interface SyncSnapshot {
  /** The Sync state, as the backend reports it; null until it first arrives. */
  status: SyncState | null;
  syncing: boolean;
  /** Why the last request failed, until the next Sync state arrives. */
  error: string | null;
  /** The result of the last Sync that finished since the app opened. */
  result: SyncResult | null;
}

/** The Sync client for one account; see `createSyncClient`. */
export interface SyncClient {
  getSnapshot(): SyncSnapshot;
  /** Hear of each new snapshot; returns the unsubscribe. */
  subscribe(listener: () => void): () => void;
  /** Hear of each finished Sync that changed the games or the Repertoire. */
  onChanged(listener: () => void): () => void;
  /** Start a Sync now (the Sync button, or Retry). */
  startSync(): Promise<void>;
  dispose(): void;
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
export function createSyncClient(backend: Backend): SyncClient {
  let snapshot: SyncSnapshot = {
    status: null,
    syncing: false,
    error: null,
    result: null,
  };
  const listeners = new Set<() => void>();
  const changeListeners = new Set<() => void>();
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  // How many Syncs had finished when we last looked, to notice a new result
  let seenRuns: number | null = null;
  let disposed = false;

  function setSnapshot(changes: Partial<SyncSnapshot>) {
    snapshot = { ...snapshot, ...changes };
    listeners.forEach((listener) => listener());
  }

  function applyStatus(status: SyncState) {
    const changes: Partial<SyncSnapshot> = {
      status,
      syncing: Boolean(status.running),
      error: null,
    };
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
    if (
      finished &&
      result &&
      (result.games_changed || result.repertoire_changed)
    ) {
      changeListeners.forEach((listener) => listener());
    }
  }

  function schedulePoll(running: boolean) {
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
  async function request(
    call: () => Promise<SyncState>,
  ): Promise<SyncState | null> {
    try {
      const status = await call();
      if (disposed) return null;
      applyStatus(status);
      return status;
    } catch (err) {
      // A Backend call rejects with an Error fit to show the user
      if (!disposed) setSnapshot({ error: (err as Error).message });
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
      return () => {
        listeners.delete(listener);
      };
    },
    onChanged(listener) {
      changeListeners.add(listener);
      return () => {
        changeListeners.delete(listener);
      };
    },
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
