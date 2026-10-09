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

// What the provider holds while no account is connected
const NO_ACCOUNT = { backend: null, client: null };

/**
 * Keeps one backend adapter and one Sync client per account: new ones when
 * the account changes.
 */
export function SyncProvider({ children }) {
  const { lichessToken, chessComUsername } = useAuth();
  const [account, setAccount] = useState(NO_ACCOUNT);

  useEffect(() => {
    if (!lichessToken || !chessComUsername) return;
    const backend = createHttpBackend({ lichessToken, chessComUsername });
    const client = createSyncClient(backend);
    setAccount({ backend, client });
    return () => {
      client.dispose();
      setAccount(NO_ACCOUNT);
    };
  }, [lichessToken, chessComUsername]);

  return <SyncContext.Provider value={account}>{children}</SyncContext.Provider>;
}

/** The Sync state, read from the account's Sync client. */
export function useSync() {
  const account = useContext(SyncContext);
  if (account === undefined) {
    throw new Error("useSync must be used within a SyncProvider");
  }
  const { backend, client } = account;

  const subscribe = useCallback(
    (listener) => (client ? client.subscribe(listener) : () => {}),
    [client],
  );
  const snapshot = useSyncExternalStore(subscribe, () =>
    client ? client.getSnapshot() : NO_SYNC,
  );
  const startSync = useCallback(() => client?.startSync(), [client]);

  return {
    backend,
    syncClient: client,
    syncStatus: snapshot.status,
    syncing: snapshot.syncing,
    syncError: snapshot.error,
    syncResult: snapshot.result,
    startSync,
    cachedGames: snapshot.status?.cached_games ?? null,
  };
}
