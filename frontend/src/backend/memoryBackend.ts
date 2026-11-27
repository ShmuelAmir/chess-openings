import type { Backend, BackendCall } from "./backend";

type Args<K extends BackendCall> = Parameters<Backend[K]>;
type Result<K extends BackendCall> = Awaited<ReturnType<Backend[K]>>;

interface Script<K extends BackendCall> {
  delayMs: number;
  settle: (args: Args<K>) => Promise<Result<K>>;
}

interface CallState<K extends BackendCall> {
  script: Script<K>;
  calls: Args<K>[];
}

/** How one call answers, from now until it is scripted again. */
export interface CallScript<K extends BackendCall> {
  answer(value: Result<K>): CallScript<K>;
  /** Answer with what `respond` returns for the call's arguments; a throw fails the call. */
  reply(
    respond: (...args: Args<K>) => Result<K> | Promise<Result<K>>,
  ): CallScript<K>;
  fail(message: string): CallScript<K>;
  delay(ms: number): CallScript<K>;
}

/** A Backend whose calls are scripted, counted and recorded. */
export interface MemoryBackend extends Backend {
  on<K extends BackendCall>(name: K): CallScript<K>;
  count(name: BackendCall): number;
  calls<K extends BackendCall>(name: K): Args<K>[];
}

const unscripted = <K extends BackendCall>(name: K): Script<K> => ({
  delayMs: 0,
  settle: () => Promise.reject(new Error(`${name} is not scripted`)),
});

const callState = <K extends BackendCall>(name: K): CallState<K> => ({
  script: unscripted(name),
  calls: [],
});

/**
 * The in-memory backend adapter, for tests and the sample mode. Each call is
 * scripted through `on(name)`: answer it, reply from its arguments, fail it,
 * or delay it. `count(name)` says how often
 * it was called, and `calls(name)` with what arguments each time.
 *
 *   backend.on("readSyncState").answer(state);
 *   backend.on("startSync").fail("Sync failed");
 *   backend.on("readSyncState").delay(500).answer(state);
 *   backend.on("loadRecallView").reply((filters) => viewFor(filters));
 *
 * A script stays in force until the call is scripted again. A call answers
 * with the script in force when it was made.
 */
export function createMemoryBackend(): MemoryBackend {
  const state: { [K in BackendCall]: CallState<K> } = {
    readSyncState: callState("readSyncState"),
    startSync: callState("startSync"),
    loadRecallView: callState("loadRecallView"),
    loadPracticeQueue: callState("loadPracticeQueue"),
    recordDrillAttempt: callState("recordDrillAttempt"),
  };

  // The call itself: a plain closure, since callers pass it around unbound
  const call =
    <K extends BackendCall>(name: K) =>
    (...args: Args<K>): Promise<Result<K>> => {
      state[name].calls.push(args);
      const { delayMs, settle } = state[name].script;
      if (!delayMs) return settle(args);
      return new Promise((resolve) => setTimeout(resolve, delayMs)).then(() =>
        settle(args),
      );
    };

  return {
    readSyncState: call("readSyncState"),
    startSync: call("startSync"),
    loadRecallView: call("loadRecallView"),
    loadPracticeQueue: call("loadPracticeQueue"),
    recordDrillAttempt: call("recordDrillAttempt"),

    on<K extends BackendCall>(name: K): CallScript<K> {
      // A fresh script: the earlier answer and delay no longer apply
      const script: Script<K> = unscripted(name);
      state[name].script = script;
      const handle: CallScript<K> = {
        answer(value) {
          script.settle = () => Promise.resolve(value);
          return handle;
        },
        reply(respond) {
          script.settle = (args) =>
            Promise.resolve().then(() => respond(...args));
          return handle;
        },
        fail(message) {
          script.settle = () => Promise.reject(new Error(message));
          return handle;
        },
        delay(ms) {
          script.delayMs = ms;
          return handle;
        },
      };
      return handle;
    },
    count: (name) => state[name].calls.length,
    calls: (name) => state[name].calls,
  };
}
