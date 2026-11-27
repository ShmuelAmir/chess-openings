import {
  createContext,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";
import type { ApiErrorBody } from "../backend/backend";
import { errorMessage } from "../errorMessage";
import { useSampleAccount } from "./SampleAccountContext";

/**
 * The signed-in Lichess account, as `/api/lichess/me` passes on Lichess's
 * account JSON. Only the fields the app reads are listed; Lichess sends more.
 */
export interface LichessUser {
  id: string;
  username: string;
}

/** Who the app is signed in as, and the ways to change that. */
export interface Auth {
  lichessToken: string | null;
  lichessUser: LichessUser | null;
  chessComUsername: string;
  /** Signed in to Lichess, with a Chess.com username saved */
  isConnected: boolean;
  handleLogin: (token: string) => void;
  handleLogout: () => void;
  /** Resolves true once the username is verified on Chess.com and saved */
  handleChessComSave: (username: string) => Promise<boolean>;
  handleChessComClear: () => void;
  chessComError: string | null;
  validatingChessCom: boolean;
}

const AuthContext = createContext<Auth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // The sample mode is signed in as the sample account for good. Its token
  // is never sent: SyncProvider uses the sample account's own backend
  const sampleAccount = useSampleAccount();
  const [lichessToken, setLichessToken] = useState<string | null>(
    sampleAccount ? "sample" : localStorage.getItem("lichess_token"),
  );
  const [lichessUser, setLichessUser] = useState<LichessUser | null>(
    sampleAccount?.lichessUser ?? null,
  );
  const [chessComUsername, setChessComUsername] = useState(
    sampleAccount?.chessComUsername ??
      (localStorage.getItem("chess_com_username") || ""),
  );

  const [chessComError, setChessComError] = useState<string | null>(null);
  const [validatingChessCom, setValidatingChessCom] = useState(false);

  // Fetch Lichess user info when token is available
  useEffect(() => {
    if (lichessToken && !sampleAccount) {
      fetchLichessUser();
    }
  }, [lichessToken, sampleAccount]);

  const fetchLichessUser = async () => {
    try {
      const response = await fetch("/api/lichess/me", {
        headers: { Authorization: `Bearer ${lichessToken}` },
      });
      if (response.ok) {
        const user: LichessUser = await response.json();
        setLichessUser(user);
      } else {
        // Token invalid, clear it
        handleLogout();
      }
    } catch (err) {
      console.error("Failed to fetch Lichess user:", err);
    }
  };

  const handleLogin = (token: string) => {
    localStorage.setItem("lichess_token", token);
    setLichessToken(token);
  };

  // Signing out of the sample account would leave nothing to sign in to
  const handleLogout = () => {
    if (sampleAccount) return;
    localStorage.removeItem("lichess_token");
    setLichessToken(null);
    setLichessUser(null);
  };

  // Verify the account exists before storing it, so a typo (or an email
  // address) doesn't silently turn into an unsyncable account.
  const handleChessComSave = async (username: string) => {
    setChessComError(null);
    setValidatingChessCom(true);
    try {
      const response = await fetch(
        `/api/chess-com/validate/${encodeURIComponent(username)}`,
      );
      if (!response.ok) {
        const data: ApiErrorBody = await response.json().catch(() => ({}));
        setChessComError(
          data.detail || `Could not verify '${username}' on Chess.com`,
        );
        return false;
      }
      localStorage.setItem("chess_com_username", username);
      setChessComUsername(username);
      return true;
    } catch (err) {
      setChessComError(errorMessage(err));
      return false;
    } finally {
      setValidatingChessCom(false);
    }
  };

  const handleChessComClear = () => {
    if (sampleAccount) return;
    localStorage.removeItem("chess_com_username");
    setChessComUsername("");
    setChessComError(null);
  };

  const isConnected = Boolean(lichessToken && lichessUser && chessComUsername);

  const value: Auth = {
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

export function useAuth(): Auth {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
