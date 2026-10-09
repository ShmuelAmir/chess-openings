const CALLS = [
  "readSyncState",
  "startSync",
  "loadRecallView",
  "loadPracticeQueue",
  "recordDrillAttempt",
];

const unscripted = (name) => ({
  delayMs: 0,
  settle: () => Promise.reject(new Error(`${name} is not scripted`)),
});

/**
 * The in-memory backend adapter, for tests. Each call is scripted through
 * `on(name)`: answer it, fail it, or delay it. `count(name)` says how often
 * it was called, and `calls(name)` with what arguments each time.
 *
 *   backend.on("readSyncState").answer(state);
 *   backend.on("startSync").fail("Sync failed");
 *   backend.on("readSyncState").delay(500).answer(state);
 *
 * A script stays in force until the call is scripted again. A call answers
 * with the script in force when it was made.
 */
export function createMemoryBackend() {
  const scripts = {};
  const calls = {};
  const backend = {};

  for (const name of CALLS) {
    calls[name] = [];
    scripts[name] = unscripted(name);

    backend[name] = (...args) => {
      calls[name].push(args);
      const { delayMs, settle } = scripts[name];
      if (!delayMs) return settle();
      return new Promise((resolve) => setTimeout(resolve, delayMs)).then(settle);
    };
  }

  backend.on = (name) => {
    // A fresh script: the earlier answer and delay no longer apply
    const script = (scripts[name] = unscripted(name));
    const handle = {
      answer(value) {
        script.settle = () => Promise.resolve(value);
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
  };

  backend.count = (name) => calls[name].length;
  backend.calls = (name) => calls[name];

  return backend;
}
