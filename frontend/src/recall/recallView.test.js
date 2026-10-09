import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryBackend } from "../backend/memoryBackend";
import { createSyncClient } from "../sync/syncClient";
import { createRecallView } from "./recallView";

const NOW = new Date("2026-10-09T12:00:00Z");

/** A Sync state as the backend reports it: idle and synced just now. */
function syncState(overrides = {}) {
  return {
    running: false,
    runs: 0,
    progress: null,
    last_synced_at: NOW.getTime() / 1000,
    cached_games: 120,
    sources: {},
    result: null,
    ...overrides,
  };
}

function gap(positionKey, status = "open") {
  return { position_key: positionKey, status };
}

function study(id) {
  return { id, name: id, opening_name: id, color: "white", gaps: 1 };
}

/** A recall view as the backend reports it. */
function recallView({ gaps = [], studies = [study("italian")] } = {}) {
  return { studies, gaps, totals: { analysed: 40 } };
}

/** Let the backend's answers that are already due reach the recall view. */
const settle = () => vi.advanceTimersByTimeAsync(0);

describe("recall view", () => {
  let backend;
  let syncClient;
  let view;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    backend = createMemoryBackend();
    backend.on("readSyncState").answer(syncState());
    syncClient = createSyncClient(backend);
  });

  afterEach(() => {
    view?.dispose();
    syncClient.dispose();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  async function open() {
    view = createRecallView({ backend, syncClient });
    await settle();
    return view;
  }

  /** Browser storage that remembers what it is given. */
  function stubStorage(initial = {}) {
    const items = new Map(Object.entries(initial));
    vi.stubGlobal("localStorage", {
      getItem: (key) => items.get(key) ?? null,
      setItem: (key, value) => items.set(key, value),
    });
    return items;
  }

  describe("on open", () => {
    it("loads the ranked Recall Gaps and totals under the default Game Filters", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));

      view = createRecallView({ backend, syncClient });
      expect(view.getSnapshot().loading).toBe(true);
      expect(view.getSnapshot().view).toBeNull();
      await settle();

      expect(backend.calls("loadRecallView")).toEqual([
        [{ timeClasses: ["blitz", "rapid"], dateRange: "3months", ratedOnly: true, studies: [] }],
      ]);
      expect(view.getSnapshot().loading).toBe(false);
      expect(view.getSnapshot().view.totals).toEqual({ analysed: 40 });
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a", "b"]);
    });
  });

  describe("changing a Game Filter", () => {
    const BULLET = { timeClasses: ["bullet"], dateRange: "year", ratedOnly: false, studies: [] };

    it("reloads the view under the new filters", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      backend.on("loadRecallView").answer(recallView({ gaps: [gap("b")] }));
      view.setFilters(BULLET);
      expect(view.getSnapshot().filters).toEqual(BULLET);
      expect(view.getSnapshot().loading).toBe(true);
      await settle();

      expect(backend.calls("loadRecallView")[1]).toEqual([BULLET]);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["b"]);
    });

    it("remembers the filters in the browser for the next visit", async () => {
      stubStorage();
      backend.on("loadRecallView").answer(recallView());
      await open();
      view.setFilters(BULLET);
      view.dispose();

      await open();

      expect(view.getSnapshot().filters).toEqual(BULLET);
      expect(backend.calls("loadRecallView").at(-1)).toEqual([BULLET]);
    });
  });

  describe("when loads overlap", () => {
    it("lets only the latest load update the view", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      backend.on("loadRecallView").delay(500).answer(recallView({ gaps: [gap("slow")] }));
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });
      backend.on("loadRecallView").delay(100).answer(recallView({ gaps: [gap("latest")] }));
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "all" });

      await vi.advanceTimersByTimeAsync(100);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["latest"]);
      expect(view.getSnapshot().loading).toBe(false);

      await vi.advanceTimersByTimeAsync(400);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["latest"]);
    });

    it("keeps loading until the latest load answers", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      backend.on("loadRecallView").delay(100).answer(recallView({ gaps: [gap("early")] }));
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });
      backend.on("loadRecallView").delay(500).answer(recallView({ gaps: [gap("latest")] }));
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "all" });

      await vi.advanceTimersByTimeAsync(100);
      expect(view.getSnapshot().loading).toBe(true);
      expect(view.getSnapshot().shownGaps).toEqual([]);

      await vi.advanceTimersByTimeAsync(400);
      expect(view.getSnapshot().loading).toBe(false);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["latest"]);
    });
  });

  describe("remembered Game Filters", () => {
    const DEFAULTS = { timeClasses: ["blitz", "rapid"], dateRange: "3months", ratedOnly: true, studies: [] };
    const KEY = "recall-view.game-filters";

    beforeEach(() => backend.on("loadRecallView").answer(recallView()));

    it("fall back to the defaults when nothing is remembered", async () => {
      stubStorage();

      await open();

      expect(view.getSnapshot().filters).toEqual(DEFAULTS);
    });

    it("fall back to the defaults when what is remembered is not readable", async () => {
      stubStorage({ [KEY]: "{not json" });

      await open();

      expect(view.getSnapshot().filters).toEqual(DEFAULTS);
    });

    it("fall back to the default for each invalid filter, keeping the valid ones", async () => {
      stubStorage({
        [KEY]: JSON.stringify({
          timeClasses: ["bullet", "hyperbullet"],
          dateRange: "decade",
          ratedOnly: false,
          studies: ["italian"],
        }),
      });

      await open();

      expect(view.getSnapshot().filters).toEqual({
        timeClasses: ["blitz", "rapid"],
        dateRange: "3months",
        ratedOnly: false,
        studies: ["italian"],
      });
    });

    it("are done without when browser storage is unavailable", async () => {
      const unavailable = () => {
        throw new Error("storage is blocked");
      };
      vi.stubGlobal("localStorage", { getItem: unavailable, setItem: unavailable });

      await open();
      expect(view.getSnapshot().filters).toEqual(DEFAULTS);

      const year = { ...DEFAULTS, dateRange: "year" };
      view.setFilters(year);
      await settle();

      expect(view.getSnapshot().filters).toEqual(year);
      expect(backend.calls("loadRecallView").at(-1)).toEqual([year]);
    });
  });

  describe("selected studies that left the Repertoire", () => {
    const withStudies = (studies) => ({
      timeClasses: ["blitz", "rapid"],
      dateRange: "3months",
      ratedOnly: true,
      studies,
    });

    it("are forgotten, and the view reloads without them", async () => {
      const remembered = stubStorage();
      backend.on("loadRecallView").answer(recallView({ studies: [study("italian"), study("caro")] }));
      await open();

      view.setFilters(withStudies(["italian", "deleted"]));
      await settle();

      expect(view.getSnapshot().filters.studies).toEqual(["italian"]);
      expect(backend.calls("loadRecallView").at(-1)).toEqual([withStudies(["italian"])]);
      expect(backend.count("loadRecallView")).toBe(3);
      expect(view.getSnapshot().loading).toBe(false);
      expect(JSON.parse(remembered.get("recall-view.game-filters")).studies).toEqual(["italian"]);
    });

    it("are kept when the returned study list is empty", async () => {
      backend.on("loadRecallView").answer(recallView({ studies: [], gaps: [] }));
      await open();

      view.setFilters(withStudies(["italian"]));
      await settle();

      expect(view.getSnapshot().filters.studies).toEqual(["italian"]);
      expect(backend.count("loadRecallView")).toBe(2);
      expect(view.getSnapshot().view.studies).toEqual([]);
    });
  });

  describe("a load that fails", () => {
    it("shows the wait-and-retry message when Lichess rate-limits it", async () => {
      backend
        .on("loadRecallView")
        .fail("Lichess rate limit reached. Please wait a minute and try again.");

      await open();

      expect(view.getSnapshot().error).toBe(
        "Lichess rate limit reached. Please wait a minute and try again.",
      );
      expect(view.getSnapshot().loading).toBe(false);
    });

    it("shows the backend's reason, and keeps the view it had", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();
      expect(view.getSnapshot().error).toBeNull();

      backend.on("loadRecallView").fail("Lichess token expired");
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });
      await settle();

      expect(view.getSnapshot().error).toBe("Lichess token expired");
      expect(view.getSnapshot().loading).toBe(false);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a"]);
    });

    it("stops showing its reason once the next load starts", async () => {
      backend.on("loadRecallView").fail("Lichess token expired");
      await open();

      backend.on("loadRecallView").delay(500).answer(recallView());
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });

      expect(view.getSnapshot().error).toBeNull();
    });

    it("is ignored when a later load is under way", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      backend.on("loadRecallView").delay(100).fail("Lichess token expired");
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });
      backend.on("loadRecallView").delay(500).answer(recallView());
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "all" });
      await vi.advanceTimersByTimeAsync(100);

      expect(view.getSnapshot().error).toBeNull();
      expect(view.getSnapshot().loading).toBe(true);
    });
  });

  /** Run a Sync to its end, with the given result. */
  async function finishSync(result) {
    const runs = syncClient.getSnapshot().status.runs;
    backend.on("startSync").answer(syncState({ running: true, runs }));
    await syncClient.startSync();
    backend.on("readSyncState").answer(syncState({ runs: runs + 1, result }));
    await vi.advanceTimersByTimeAsync(1000);
  }

  const CHANGED = { games_changed: true, repertoire_changed: false, new_games: 4 };

  describe("a Sync", () => {
    it("reloads the view when it changed something", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("new")] }));
      await finishSync(CHANGED);

      expect(backend.count("loadRecallView")).toBe(2);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a", "new"]);
    });

    it("does not reload the view when it changed nothing", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      await finishSync({ games_changed: false, repertoire_changed: false, new_games: 0 });

      expect(backend.count("loadRecallView")).toBe(1);
    });
  });

  describe("while held", () => {
    it("keeps a Sync's change back until released", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      view.hold();
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("new")] }));
      await finishSync(CHANGED);
      expect(backend.count("loadRecallView")).toBe(1);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a"]);

      view.release();
      await settle();
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a", "new"]);
    });

    it("drops a load that was under way and runs it again once released", async () => {
      backend.on("loadRecallView").delay(500).answer(recallView({ gaps: [gap("a")] }));
      view = createRecallView({ backend, syncClient });

      view.hold();
      expect(view.getSnapshot().loading).toBe(false);
      await vi.advanceTimersByTimeAsync(500);
      expect(view.getSnapshot().view).toBeNull();

      view.release();
      await vi.advanceTimersByTimeAsync(500);
      expect(backend.count("loadRecallView")).toBe(2);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a"]);
    });

    it("does not reload on release when nothing was kept back", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      view.hold();
      view.release();
      await settle();

      expect(backend.count("loadRecallView")).toBe(1);
    });
  });

  describe("Closed Recall Gaps", () => {
    beforeEach(() =>
      backend
        .on("loadRecallView")
        .answer(recallView({ gaps: [gap("a"), gap("b", "closed"), gap("c"), gap("d", "closed")] })),
    );

    it("are hidden, and counted, until toggled on", async () => {
      await open();

      expect(view.getSnapshot().showClosed).toBe(false);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a", "c"]);
      expect(view.getSnapshot().closedCount).toBe(2);
    });

    it("are shown in ranking order once toggled on, and hidden again when toggled off", async () => {
      await open();

      view.toggleClosed();
      expect(view.getSnapshot().showClosed).toBe(true);
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a", "b", "c", "d"]);

      view.toggleClosed();
      expect(view.getSnapshot().shownGaps.map((g) => g.position_key)).toEqual(["a", "c"]);
    });
  });

  describe("the selected Recall Gap", () => {
    it("is the first shown gap until one is selected", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a", "closed"), gap("b"), gap("c")] }));
      await open();

      expect(view.getSnapshot().selected.position_key).toBe("b");
    });

    it("is none when no gap is shown", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [] }));
      await open();

      expect(view.getSnapshot().selected).toBeUndefined();
    });

    it("stays selected across a reload while it is still listed", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.selectGap("b");
      expect(view.getSnapshot().selected.position_key).toBe("b");

      backend.on("loadRecallView").answer(recallView({ gaps: [gap("new"), gap("a"), gap("b")] }));
      await finishSync(CHANGED);

      expect(view.getSnapshot().selected.position_key).toBe("b");
    });

    it("falls back to the first shown gap when a reload no longer lists it", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.selectGap("b");

      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("c")] }));
      await finishSync(CHANGED);

      expect(view.getSnapshot().selected.position_key).toBe("a");
    });

    it("falls back to the first shown gap when it is Closed and Closed gaps are hidden again", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b", "closed")] }));
      await open();
      view.toggleClosed();
      view.selectGap("b");
      expect(view.getSnapshot().selected.position_key).toBe("b");

      view.toggleClosed();

      expect(view.getSnapshot().selected.position_key).toBe("a");
    });
  });

  describe("subscribers", () => {
    it("hear of each new snapshot until they unsubscribe", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      const heard = vi.fn();
      const unsubscribe = view.subscribe(heard);

      view.selectGap("b");
      expect(heard).toHaveBeenCalledTimes(1);

      unsubscribe();
      view.toggleClosed();
      expect(heard).toHaveBeenCalledTimes(1);
    });
  });

  describe("once disposed", () => {
    it("ignores a load that was still on its way", async () => {
      backend.on("loadRecallView").delay(500).answer(recallView({ gaps: [gap("a")] }));
      view = createRecallView({ backend, syncClient });
      const heard = vi.fn();
      view.subscribe(heard);
      heard.mockClear();

      view.dispose();
      await vi.advanceTimersByTimeAsync(500);

      expect(view.getSnapshot().view).toBeNull();
      expect(heard).not.toHaveBeenCalled();
    });

    it("no longer reloads after a Sync", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      view.dispose();
      await finishSync(CHANGED);

      expect(backend.count("loadRecallView")).toBe(1);
    });

    it("does not load when the Game Filters are changed", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      view.dispose();
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });

      expect(backend.count("loadRecallView")).toBe(1);
    });
  });
});
