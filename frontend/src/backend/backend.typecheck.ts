// Type-only checks of the frontend backend seam, run by `tsc` (`make lint`),
// never by Vitest. Each `@ts-expect-error` line must stay a type error: if one
// starts compiling, the seam has stopped catching that mistake.
import type { Backend, RecallView, SyncState } from "./backend";
import { createHttpBackend } from "./httpBackend";
import { createMemoryBackend } from "./memoryBackend";

declare const syncState: SyncState;
declare const recallView: RecallView;

// Both adapters implement the whole contract
const http: Backend = createHttpBackend({
  lichessToken: "token",
  chessComUsername: "user",
});
const memory: Backend = createMemoryBackend();

const backend = createMemoryBackend();

// Only real call names can be scripted, counted or inspected
// @ts-expect-error not a call of the Backend
backend.on("misspelled");
// @ts-expect-error not a call of the Backend
backend.count("readSyncStat");
// @ts-expect-error not a call of the Backend
backend.calls("loadRecalView");

// An answer must have the call's result shape
backend.on("readSyncState").answer(syncState);
// @ts-expect-error a Recall view is not a Sync state
backend.on("readSyncState").answer(recallView);
// @ts-expect-error the practice queue is a list of Recall Gaps
backend.on("loadPracticeQueue").answer(recallView);

// A reply gets the call's arguments and must return its result shape
backend.on("loadRecallView").reply((filters) => {
  const ratedOnly: boolean = filters.ratedOnly;
  return { ...recallView, studies: ratedOnly ? recallView.studies : [] };
});
// @ts-expect-error a reply must return the call's result
backend.on("startSync").reply(() => recallView);
backend.on("startSync").delay(10).fail("Sync failed").answer(syncState);

// Recorded arguments are typed per call
const [attempt] = backend.calls("recordDrillAttempt")[0];
const passed: boolean = attempt.passed;
// @ts-expect-error readSyncState takes no arguments
const [none] = backend.calls("readSyncState")[0];

export { http, memory, passed, none };
