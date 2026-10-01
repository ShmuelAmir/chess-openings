import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { syncOrchestrator } from "./SyncOrchestrator";

const AuthContext = createContext(null);

// Sync on open when the older source's last Sync is older than this
const SYNC_STALE_SECONDS = 10 * 60;
const SYNC_POLL_MS = 1000;

function isStale(lastSyncedAt) {
  return !lastSyncedAt || Date.now() / 1000 - lastSyncedAt > SYNC_STALE_SECONDS;
}

export function AuthProvider({ children }) {
  const [lichessToken, setLichessToken] = useState(
    localStorage.getItem("lichess_token"),
  );
  const [lichessUser, setLichessUser] = useState(null);
  const [chessComUsername, setChessComUsername] = useState(
    localStorage.getItem("chess_com_username") || "",
  );

  // Sync state, as GET /api/sync reports it
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncError, setSyncError] = useState(null);
  // The result of the last Sync that finished since the app opened
  const [syncResult, setSyncResult] = useState(null);
  const [chessComError, setChessComError] = useState(null);
  const [validatingChessCom, setValidatingChessCom] = useState(false);

  // Fetch Lichess user info when token is available
  useEffect(() => {
    if (lichessToken) {
      fetchLichessUser();
    }
  }, [lichessToken]);

  const fetchLichessUser = async () => {
    try {
      const response = await fetch("/api/lichess/me", {
        headers: { Authorization: `Bearer ${lichessToken}` },
      });
      if (response.ok) {
        const user = await response.json();
        setLichessUser(user);
      } else {
        // Token invalid, clear it
        handleLogout();
      }
    } catch (err) {
      console.error("Failed to fetch Lichess user:", err);
    }
  };

  const handleLogin = (token) => {
    localStorage.setItem("lichess_token", token);
    setLichessToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem("lichess_token");
    setLichessToken(null);
    setLichessUser(null);
  };

  // Verify the account exists before storing it, so a typo (or an email
  // address) doesn't silently turn into an unsyncable account.
  const handleChessComSave = async (username) => {
    setChessComError(null);
    setValidatingChessCom(true);
    try {
      const response = await fetch(`/api/chess-com/validate/${encodeURIComponent(username)}`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setChessComError(data.detail || `Could not verify '${username}' on Chess.com`);
        return false;
      }
      localStorage.setItem("chess_com_username", username);
      setChessComUsername(username);
      return true;
    } catch (err) {
      setChessComError(err.message);
      return false;
    } finally {
      setValidatingChessCom(false);
    }
  };

  const handleChessComClear = () => {
    localStorage.removeItem("chess_com_username");
    setChessComUsername("");
    setSyncStatus(null);
    setChessComError(null);
    setSyncError(null);
    setSyncResult(null);
    syncOrchestrator.notifyCacheCleared();
  };

  const syncRequest = useCallback(
    async (method = "GET") => {
      const params = new URLSearchParams({ chess_com_username: chessComUsername });
      const response = await fetch(`/api/sync?${params}`, {
        method,
        headers: { Authorization: `Bearer ${lichessToken}` },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Sync failed");
      }
      return response.json();
    },
    [chessComUsername, lichessToken],
  );

  // How many Syncs had finished when we last looked, to notice a new result
  const seenRunsRef = useRef(null);

  const applySyncStatus = useCallback((status) => {
    setSyncStatus(status);
    setSyncError(null);
    if (seenRunsRef.current === null) {
      seenRunsRef.current = status.runs;
    } else if (!status.running && status.runs > seenRunsRef.current) {
      seenRunsRef.current = status.runs;
      const result = status.result;
      setSyncResult(result);
      // Re-run the analysis only if the Sync changed something
      if (result && (result.games_changed || result.repertoire_changed)) {
        syncOrchestrator.notifyCacheReady();
      }
    }
  }, []);

  // Start a Sync now (the Sync button, or Retry)
  const startSync = useCallback(async () => {
    setSyncError(null);
    try {
      applySyncStatus(await syncRequest("POST"));
    } catch (err) {
      setSyncError(err.message);
      syncOrchestrator.notifySyncError(err);
    }
  }, [syncRequest, applySyncStatus]);

  // On app open: Sync if the older source's last Sync is stale
  useEffect(() => {
    if (!lichessToken || !chessComUsername) return;
    let cancelled = false;
    seenRunsRef.current = null;

    (async () => {
      try {
        const status = await syncRequest();
        if (cancelled) return;
        applySyncStatus(status);
        if (!status.running && isStale(status.last_synced_at)) {
          const started = await syncRequest("POST");
          if (!cancelled) applySyncStatus(started);
        }
      } catch (err) {
        if (!cancelled) setSyncError(err.message);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [lichessToken, chessComUsername, syncRequest, applySyncStatus]);

  // Poll the Sync's progress while it runs
  const syncing = Boolean(syncStatus?.running);
  useEffect(() => {
    if (!syncing) return;
    const id = setInterval(async () => {
      try {
        applySyncStatus(await syncRequest());
      } catch (err) {
        setSyncError(err.message);
      }
    }, SYNC_POLL_MS);
    return () => clearInterval(id);
  }, [syncing, syncRequest, applySyncStatus]);

  const isConnected = lichessToken && lichessUser && chessComUsername;

  const value = {
    lichessToken,
    lichessUser,
    chessComUsername,
    isConnected,
    handleLogin,
    handleLogout,
    handleChessComSave,
    handleChessComClear,
    // Sync
    syncStatus,
    syncing,
    syncError,
    syncResult,
    startSync,
    cachedGames: syncStatus?.cached_games ?? null,
    chessComError,
    validatingChessCom,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
