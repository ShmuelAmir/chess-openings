// Type-only checks of the router and contexts, run by `tsc` (`make lint`),
// never by Vitest. Each `@ts-expect-error` line must stay a type error: if one
// starts compiling, the router or a context has stopped catching that mistake.
import { Link, useNavigate } from "@tanstack/react-router";
import type { Backend, SyncState } from "./backend/backend";
import { useAuth } from "./context/AuthContext";
import type { LichessUser } from "./context/AuthContext";
import { useSampleAccount } from "./context/SampleAccountContext";
import { useSync } from "./context/SyncContext";
import type { SampleAccount } from "./sample/sampleAccount";

// Links reach only the routes the router registers
export const links = (
  <>
    <Link to="/">Recall</Link>
    <Link to="/openings">Openings</Link>
    <Link to="/settings">Settings</Link>
    {/* @ts-expect-error not a route of the app */}
    <Link to="/nowhere">Nowhere</Link>
    {/* @ts-expect-error a misspelled route */}
    <Link to="/setting">Settings</Link>
  </>
);

export function useNavigation() {
  const navigate = useNavigate();
  navigate({ to: "/openings" });
  // @ts-expect-error not a route of the app
  navigate({ to: "/nowhere" });
}

// Each context hands back its value's type, no cast needed
export function useContexts() {
  const { lichessUser, isConnected, handleChessComSave } = useAuth();
  const user: LichessUser | null = lichessUser;
  const connected: boolean = isConnected;
  const saved: Promise<boolean> = handleChessComSave("someone");
  // @ts-expect-error the username is a string
  handleChessComSave(42);

  const { backend, syncStatus, cachedGames } = useSync();
  const maybeBackend: Backend | null = backend;
  const status: SyncState | null = syncStatus;
  const games: number | null = cachedGames;
  // @ts-expect-error the backend may be missing while no account is connected
  const sureBackend: Backend = backend;

  const sample: SampleAccount | null = useSampleAccount();
  // @ts-expect-error there's no sample account outside the sample mode
  const sureSample: SampleAccount = useSampleAccount();

  return [
    user,
    connected,
    saved,
    maybeBackend,
    status,
    games,
    sureBackend,
    sample,
    sureSample,
  ];
}

// The sample account is signed in as a Lichess user like any other
export const sampleUser = (account: SampleAccount): LichessUser =>
  account.lichessUser;
