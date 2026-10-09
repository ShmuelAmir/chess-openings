import { createContext, useContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [lichessToken, setLichessToken] = useState(
    localStorage.getItem("lichess_token"),
  );
  const [lichessUser, setLichessUser] = useState(null);
  const [chessComUsername, setChessComUsername] = useState(
    localStorage.getItem("chess_com_username") || "",
  );

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
    setChessComError(null);
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
