import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [lichessToken, setLichessToken] = useState(
    localStorage.getItem("lichess_token"),
  );
  const [lichessUser, setLichessUser] = useState(null);
  const [chessComUsername, setChessComUsername] = useState(
    localStorage.getItem("chess_com_username") || "",
  );

  // Cache/sync state
  const [cacheStatus, setCacheStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);

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

  const handleChessComSave = (username) => {
    localStorage.setItem("chess_com_username", username);
    setChessComUsername(username);
  };

  const handleChessComClear = () => {
    localStorage.removeItem("chess_com_username");
    setChessComUsername("");
    setCacheStatus(null);
  };

  // Fetch cache status
  const fetchCacheStatus = useCallback(async () => {
    if (!chessComUsername) {
      setCacheStatus(null);
      return;
    }
    try {
      const response = await fetch(
        `/api/chess-com/cache-status/${chessComUsername}`,
      );
      if (response.ok) {
        const data = await response.json();
        setCacheStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch cache status:", err);
    }
  }, [chessComUsername]);

  // Fetch cache status when username changes
  useEffect(() => {
    fetchCacheStatus();
  }, [fetchCacheStatus]);

  // Sync games from Chess.com
  const syncGames = async () => {
    if (!chessComUsername || syncing) return;

    setSyncing(true);
    setSyncError(null);

    try {
      const response = await fetch(`/api/chess-com/sync/${chessComUsername}`, {
        method: "POST",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Sync failed");
      }

      await fetchCacheStatus();
    } catch (err) {
      setSyncError(err.message);
    } finally {
      setSyncing(false);
    }
  };

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
    // Cache/sync
    cacheStatus,
    syncing,
    syncError,
    syncGames,
    fetchCacheStatus,
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
