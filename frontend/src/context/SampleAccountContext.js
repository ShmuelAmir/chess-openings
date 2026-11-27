import { createContext, useContext } from "react";

/**
 * The sample account in the sample mode (`npm run dev:sample`), else null.
 * When set, the app is signed in as it and talks to its in-memory backend:
 * no Lichess sign-in, no Chess.com username, no backend server.
 */
export const SampleAccountContext = createContext(null);

export const useSampleAccount = () => useContext(SampleAccountContext);
