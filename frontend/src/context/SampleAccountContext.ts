import { createContext, useContext } from "react";
// `import type` only: the sample account itself stays out of other builds
import type { SampleAccount } from "../sample/sampleAccount";

/**
 * The sample account in the sample mode (`npm run dev:sample`), else null.
 * When set, the app is signed in as it and talks to its in-memory backend:
 * no Lichess sign-in, no Chess.com username, no backend server.
 */
export const SampleAccountContext = createContext<SampleAccount | null>(null);

export const useSampleAccount = (): SampleAccount | null =>
  useContext(SampleAccountContext);
