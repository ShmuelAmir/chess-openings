import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";
import { useAuth } from "./AuthContext";
import { createHttpBackend } from "../backend/httpBackend";
import { createSyncClient } from "../sync/syncClient";

const SyncContext = createContext(undefined);

// What there is to show while no account is connected
const NO_SYNC = { status: null, syncing: false, error: null, result: null };

/** Keeps one Sync client per account: a new one when the account changes. */
export function SyncProvider({ children }) {
  const { lichessToken, chessComUsername } = useAuth();
  const [client, setClient] = useState(null);

  useEffect(() => {
    if (!lichessToken || !chessComUsername) return;
    const created = createSyncClient(createHttpBackend({ lichessToken, chessComUsername }));
    setClient(created);
    return () => {
      created.dispose();
      setClient(null);
    };
  }, [lichessToken, chessComUsername]);

  return <SyncContext.Provider value={client}>{children}</SyncContext.Provider>;
}

/** The Sync state, read from the account's Sync client. */
export function useSync() {
  const client = useContext(SyncContext);
  if (client === undefined) {
    throw new Error("useSync must be used within a SyncProvider");
  }

  const subscribe = useCallback(
    (listener) => (client ? client.subscribe(listener) : () => {}),
    [client],
  );
  const snapshot = useSyncExternalStore(subscribe, () =>
    client ? client.getSnapshot() : NO_SYNC,
  );
  const startSync = useCallback(() => client?.startSync(), [client]);

  return {
    syncClient: client,
    syncStatus: snapshot.status,
    syncing: snapshot.syncing,
    syncError: snapshot.error,
    syncResult: snapshot.result,
    startSync,
    cachedGames: snapshot.status?.cached_games ?? null,
  };
}
