import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryBackend } from "../backend/memoryBackend";
import { createSyncClient } from "./syncClient";

const NOW = new Date("2026-10-09T12:00:00Z");
const NOW_SECONDS = NOW.getTime() / 1000;
const MINUTE = 60;

/** A Sync state as the backend reports it; synced a minute ago unless told otherwise. */
function syncState(overrides = {}) {
  return {
    running: false,
    runs: 0,
    progress: null,
    last_synced_at: NOW_SECONDS - MINUTE,
    cached_games: 120,
    sources: {},
    result: null,
    ...overrides,
  };
}

const UNCHANGED = { games_changed: false, repertoire_changed: false, new_games: 0 };

/** Let the backend's answers that are already due reach the client. */
const settle = () => vi.advanceTimersByTimeAsync(0);

/** One poll interval. */
const second = () => vi.advanceTimersByTimeAsync(1000);

describe("Sync client", () => {
  let backend;
  let client;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    backend = createMemoryBackend();
  });

  afterEach(() => {
    client?.dispose();
    vi.useRealTimers();
  });

  async function open() {
    client = createSyncClient(backend);
    await settle();
    return client;
  }

  describe("on open", () => {
    it("starts a Sync when the last Sync is older than ten minutes", async () => {
      backend.on("readSyncState").answer(syncState({ last_synced_at: NOW_SECONDS - 11 * MINUTE }));
      backend.on("startSync").answer(syncState({ running: true, progress: "Fetching games" }));

      await open();

      expect(backend.count("startSync")).toBe(1);
      expect(client.getSnapshot().syncing).toBe(true);
      expect(client.getSnapshot().status.progress).toBe("Fetching games");
    });

    it("starts a Sync when there has never been one", async () => {
      backend.on("readSyncState").answer(syncState({ last_synced_at: null }));
      backend.on("startSync").answer(syncState({ running: true }));

      await open();

      expect(backend.count("startSync")).toBe(1);
    });

    it("does not start a Sync when the last Sync is recent", async () => {
      backend.on("readSyncState").answer(syncState({ last_synced_at: NOW_SECONDS - 9 * MINUTE }));

      await open();

      expect(backend.count("startSync")).toBe(0);
      expect(client.getSnapshot().syncing).toBe(false);
      expect(client.getSnapshot().status.cached_games).toBe(120);
    });

    it("does not start a second Sync when one is already running", async () => {
      backend
        .on("readSyncState")
        .answer(syncState({ running: true, last_synced_at: NOW_SECONDS - 11 * MINUTE }));

      await open();

      expect(backend.count("startSync")).toBe(0);
      expect(client.getSnapshot().syncing).toBe(true);
    });
  });

  describe("while a Sync runs", () => {
    it("polls the Sync state each second and stops once the Sync finishes", async () => {
      backend.on("readSyncState").answer(syncState({ running: true, progress: "Month 1 of 3" }));
      await open();
      expect(backend.count("readSyncState")).toBe(1);

      backend.on("readSyncState").answer(syncState({ running: true, progress: "Month 2 of 3" }));
      await second();
      expect(backend.count("readSyncState")).toBe(2);
      expect(client.getSnapshot().status.progress).toBe("Month 2 of 3");

      backend.on("readSyncState").answer(syncState({ running: false, runs: 1, result: UNCHANGED }));
      await second();
      expect(backend.count("readSyncState")).toBe(3);
      expect(client.getSnapshot().syncing).toBe(false);

      await vi.advanceTimersByTimeAsync(10_000);
      expect(backend.count("readSyncState")).toBe(3);
    });

    it("does not poll while no Sync is running", async () => {
      backend.on("readSyncState").answer(syncState());
      await open();

      await vi.advanceTimersByTimeAsync(10_000);

      expect(backend.count("readSyncState")).toBe(1);
    });

    it("tells subscribers of each new state", async () => {
      backend.on("readSyncState").answer(syncState({ running: true }));
      client = createSyncClient(backend);
      const seen = [];
      client.subscribe(() => seen.push(client.getSnapshot().syncing));

      await settle();
      backend.on("readSyncState").answer(syncState({ running: false, runs: 1, result: UNCHANGED }));
      await second();

      expect(seen).toEqual([true, false]);
    });
  });

  describe("a finished Sync", () => {
    const CHANGED = { games_changed: true, repertoire_changed: false, new_games: 4 };

    it("is not reported as new when it finished before the app opened", async () => {
      backend.on("readSyncState").answer(syncState({ runs: 3, result: CHANGED }));
      const changes = vi.fn();
      client = createSyncClient(backend);
      client.onChanged(changes);

      await settle();

      expect(client.getSnapshot().result).toBeNull();
      expect(changes).not.toHaveBeenCalled();
    });

    it("has its result exposed once the Sync started on demand finishes", async () => {
      backend.on("readSyncState").answer(syncState({ runs: 3 }));
      await open();

      backend.on("startSync").answer(syncState({ running: true, runs: 3 }));
      await client.startSync();
      expect(client.getSnapshot().syncing).toBe(true);
      expect(client.getSnapshot().result).toBeNull();

      backend.on("readSyncState").answer(syncState({ runs: 4, result: CHANGED }));
      await second();

      expect(client.getSnapshot().result).toEqual(CHANGED);
    });

    it("is noticed exactly once by its run count", async () => {
      backend.on("readSyncState").answer(syncState({ running: true, runs: 0 }));
      const changes = vi.fn();
      client = createSyncClient(backend);
      client.onChanged(changes);
      await settle();

      backend.on("readSyncState").answer(syncState({ runs: 1, result: CHANGED }));
      await second();
      expect(changes).toHaveBeenCalledTimes(1);

      // The same finished Sync, read again while starting the next one
      backend.on("startSync").answer(syncState({ running: false, runs: 1, result: CHANGED }));
      await client.startSync();

      expect(changes).toHaveBeenCalledTimes(1);
    });

    it("is noticed again for each later Sync", async () => {
      backend.on("readSyncState").answer(syncState({ running: true, runs: 0 }));
      const changes = vi.fn();
      client = createSyncClient(backend);
      client.onChanged(changes);
      await settle();
      backend.on("readSyncState").answer(syncState({ runs: 1, result: CHANGED }));
      await second();

      backend.on("startSync").answer(syncState({ running: true, runs: 1, result: CHANGED }));
      await client.startSync();
      const later = { games_changed: false, repertoire_changed: true, new_games: 0 };
      backend.on("readSyncState").answer(syncState({ runs: 2, result: later }));
      await second();

      expect(changes).toHaveBeenCalledTimes(2);
      expect(client.getSnapshot().result).toEqual(later);
    });
  });

  describe("announcing that something changed", () => {
    async function finishSyncWith(result) {
      backend.on("readSyncState").answer(syncState({ running: true, runs: 0 }));
      const changes = vi.fn();
      client = createSyncClient(backend);
      client.onChanged(changes);
      await settle();
      backend.on("readSyncState").answer(syncState({ runs: 1, result }));
      await second();
      return changes;
    }

    it("happens when the Sync changed the games", async () => {
      const changes = await finishSyncWith({ games_changed: true, repertoire_changed: false });
      expect(changes).toHaveBeenCalledTimes(1);
    });

    it("happens when the Sync changed the Repertoire", async () => {
      const changes = await finishSyncWith({ games_changed: false, repertoire_changed: true });
      expect(changes).toHaveBeenCalledTimes(1);
    });

    it("does not happen when the Sync changed nothing", async () => {
      const changes = await finishSyncWith(UNCHANGED);

      expect(changes).not.toHaveBeenCalled();
      expect(client.getSnapshot().result).toEqual(UNCHANGED);
    });

    it("comes after the result is readable", async () => {
      backend.on("readSyncState").answer(syncState({ running: true, runs: 0 }));
      client = createSyncClient(backend);
      let resultWhenAnnounced;
      client.onChanged(() => (resultWhenAnnounced = client.getSnapshot().result));
      await settle();
      const result = { games_changed: true, repertoire_changed: false };
      backend.on("readSyncState").answer(syncState({ runs: 1, result }));
      await second();

      expect(resultWhenAnnounced).toEqual(result);
    });

    it("stops for a listener that unsubscribed", async () => {
      backend.on("readSyncState").answer(syncState({ running: true, runs: 0 }));
      const changes = vi.fn();
      client = createSyncClient(backend);
      const unsubscribe = client.onChanged(changes);
      await settle();
      unsubscribe();
      backend
        .on("readSyncState")
        .answer(syncState({ runs: 1, result: { games_changed: true, repertoire_changed: false } }));
      await second();

      expect(changes).not.toHaveBeenCalled();
    });
  });

  describe("a failed request", () => {
    it("surfaces as a Sync error when the Sync state cannot be read on open", async () => {
      backend.on("readSyncState").fail("Chess.com is unreachable");

      await open();

      expect(client.getSnapshot().error).toBe("Chess.com is unreachable");
      expect(client.getSnapshot().status).toBeNull();
      expect(backend.count("startSync")).toBe(0);
    });

    it("surfaces as a Sync error when the Sync on open cannot be started", async () => {
      backend.on("readSyncState").answer(syncState({ last_synced_at: null }));
      backend.on("startSync").fail("Sync failed");

      await open();

      expect(client.getSnapshot().error).toBe("Sync failed");
      expect(client.getSnapshot().syncing).toBe(false);
    });

    it("surfaces as a Sync error when a Sync started on demand fails, and clears on the next successful state", async () => {
      backend.on("readSyncState").answer(syncState());
      await open();
      expect(client.getSnapshot().error).toBeNull();

      backend.on("startSync").fail("Lichess token expired");
      await client.startSync();
      expect(client.getSnapshot().error).toBe("Lichess token expired");

      backend.on("startSync").answer(syncState({ running: true }));
      await client.startSync();
      expect(client.getSnapshot().error).toBeNull();
      expect(client.getSnapshot().syncing).toBe(true);
    });

    it("clears while a retry is under way", async () => {
      backend.on("readSyncState").answer(syncState());
      await open();
      backend.on("startSync").fail("Sync failed");
      await client.startSync();

      backend.on("startSync").delay(500).answer(syncState({ running: true }));
      client.startSync();

      expect(client.getSnapshot().error).toBeNull();
    });

    it("surfaces a failed poll, keeps polling, and clears on the next successful state", async () => {
      backend.on("readSyncState").answer(syncState({ running: true }));
      await open();

      backend.on("readSyncState").fail("Sync failed");
      await second();
      expect(client.getSnapshot().error).toBe("Sync failed");
      expect(client.getSnapshot().syncing).toBe(true);

      backend.on("readSyncState").answer(syncState({ running: true, progress: "Month 2 of 3" }));
      await second();
      expect(client.getSnapshot().error).toBeNull();
      expect(client.getSnapshot().status.progress).toBe("Month 2 of 3");
    });
  });

  describe("once disposed", () => {
    it("stops polling", async () => {
      backend.on("readSyncState").answer(syncState({ running: true }));
      await open();
      await second();
      expect(backend.count("readSyncState")).toBe(2);

      client.dispose();
      await vi.advanceTimersByTimeAsync(10_000);

      expect(backend.count("readSyncState")).toBe(2);
    });

    it("ignores an answer that was still on its way", async () => {
      backend.on("readSyncState").delay(500).answer(syncState({ running: true }));
      client = createSyncClient(backend);
      const heard = vi.fn();
      client.subscribe(heard);

      client.dispose();
      await vi.advanceTimersByTimeAsync(10_000);

      expect(client.getSnapshot().status).toBeNull();
      expect(heard).not.toHaveBeenCalled();
      expect(backend.count("readSyncState")).toBe(1);
    });

    it("does not start a Sync", async () => {
      backend.on("readSyncState").answer(syncState());
      await open();

      client.dispose();
      await client.startSync();

      expect(backend.count("startSync")).toBe(0);
    });
  });
});
