import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useAuth } from "./AuthContext";
import { useSampleAccount } from "./SampleAccountContext";
import type { Backend, SyncResult, SyncState } from "../backend/backend";
import { createHttpBackend } from "../backend/httpBackend";
import {
  createSyncClient,
  type SyncClient,
  type SyncSnapshot,
} from "../sync/syncClient";

/** The account's backend adapter and Sync client; both null with no account. */
type Account =
  { backend: Backend; client: SyncClient } | { backend: null; client: null };

/** The account's backend adapter and its Sync state, from `useSync`. */
export interface Sync {
  /** The account's backend adapter; null while no account is connected */
  backend: Backend | null;
  /** The account's Sync client; null while no account is connected */
  syncClient: SyncClient | null;
  syncStatus: SyncState | null;
  syncing: boolean;
  syncError: string | null;
  syncResult: SyncResult | null;
  /** Start a Sync now; does nothing while no account is connected */
  startSync: () => void;
  cachedGames: number | null;
}

// undefined, not null, outside a SyncProvider: null is "no account" here
const SyncContext = createContext<Account | undefined>(undefined);

// What there is to show while no account is connected
const NO_SYNC: SyncSnapshot = {
  status: null,
  syncing: false,
  error: null,
  result: null,
};

// What the provider holds while no account is connected
const NO_ACCOUNT: Account = { backend: null, client: null };

/**
 * Keeps one backend adapter and one Sync client per account: new ones when
 * the account changes. The sample mode's adapter is the sample account's.
 */
export function SyncProvider({ children }: { children: ReactNode }) {
  const { lichessToken, chessComUsername } = useAuth();
  const sampleAccount = useSampleAccount();
  const [account, setAccount] = useState<Account>(NO_ACCOUNT);

  useEffect(() => {
    if (!lichessToken || !chessComUsername) return;
    const backend =
      sampleAccount?.backend ??
      createHttpBackend({ lichessToken, chessComUsername });
    const client = createSyncClient(backend);
    setAccount({ backend, client });
    return () => {
      client.dispose();
      setAccount(NO_ACCOUNT);
    };
  }, [lichessToken, chessComUsername, sampleAccount]);

  return (
    <SyncContext.Provider value={account}>{children}</SyncContext.Provider>
  );
}

/** The Sync state, read from the account's Sync client. */
export function useSync(): Sync {
  const account = useContext(SyncContext);
  if (account === undefined) {
    throw new Error("useSync must be used within a SyncProvider");
  }
  const { backend, client } = account;

  const subscribe = useCallback(
    (listener: () => void) => (client ? client.subscribe(listener) : () => {}),
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
