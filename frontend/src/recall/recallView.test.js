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

/** A Recall Gap as the backend reports it; Open unless told otherwise. */
function gap(positionKey, status = "open") {
  return { position_key: positionKey, status };
}

/** A study of the Repertoire as the backend reports it. */
function study(id) {
  return { id, name: id, opening_name: id, color: "white", gaps: 1 };
}

/** A recall view as the backend reports it. */
function recallView({ gaps = [], studies = [study("italian")] } = {}) {
  return { studies, gaps, totals: { analysed: 40 } };
}

const DEFAULTS = { timeClasses: ["blitz", "rapid"], dateRange: "3months", ratedOnly: true, studies: [] };
const BULLET = { timeClasses: ["bullet"], dateRange: "year", ratedOnly: false, studies: [] };
const UNCHANGED = { games_changed: false, repertoire_changed: false, new_games: 0 };
// Where the browser remembers the Game Filters
const STORAGE_KEY = "recall-view.game-filters";

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

  /** The position keys of the shown Recall Gaps, in order. */
  const shownKeys = () => view.getSnapshot().shownGaps.map((gap) => gap.position_key);

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

      expect(backend.calls("loadRecallView")).toEqual([[DEFAULTS]]);
      expect(view.getSnapshot().loading).toBe(false);
      expect(view.getSnapshot().view.totals).toEqual({ analysed: 40 });
      expect(shownKeys()).toEqual(["a", "b"]);
    });
  });

  describe("changing a Game Filter", () => {
    it("reloads the view under the new filters", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      backend.on("loadRecallView").answer(recallView({ gaps: [gap("b")] }));
      view.setFilters(BULLET);
      expect(view.getSnapshot().filters).toEqual(BULLET);
      expect(view.getSnapshot().loading).toBe(true);
      await settle();

      expect(backend.calls("loadRecallView")[1]).toEqual([BULLET]);
      expect(shownKeys()).toEqual(["b"]);
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

  describe("changing a Game Filter during practice", () => {
    beforeEach(() => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      backend.on("loadPracticeQueue").answer([gap("a")]);
    });

    it("is ignored during a single drill: no reload, the filters stay, and nothing is remembered", async () => {
      const stored = stubStorage();
      await open();
      view.startDrill();

      view.setFilters(BULLET);
      await settle();

      expect(backend.count("loadRecallView")).toBe(1);
      expect(view.getSnapshot()).toMatchObject({ filters: DEFAULTS, loading: false });
      expect(stored.size).toBe(0);
    });

    it("is ignored during a practice session", async () => {
      const stored = stubStorage();
      await open();
      view.startSession();
      await settle();

      view.setFilters(BULLET);
      await settle();

      expect(backend.count("loadRecallView")).toBe(1);
      expect(view.getSnapshot().filters).toEqual(DEFAULTS);
      expect(stored.size).toBe(0);
    });

    it("reloads the view once practice has ended", async () => {
      await open();
      view.startDrill();
      // Ignored, and not kept for later
      view.setFilters(BULLET);
      view.endPractice();
      await settle();
      expect(backend.count("loadRecallView")).toBe(1);

      view.setFilters(BULLET);
      await settle();

      expect(view.getSnapshot().filters).toEqual(BULLET);
      expect(backend.calls("loadRecallView")).toEqual([[DEFAULTS], [BULLET]]);
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
      expect(shownKeys()).toEqual(["latest"]);
      expect(view.getSnapshot().loading).toBe(false);

      await vi.advanceTimersByTimeAsync(400);
      expect(shownKeys()).toEqual(["latest"]);
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
      expect(shownKeys()).toEqual(["latest"]);
    });
  });

  describe("remembered Game Filters", () => {
    beforeEach(() => backend.on("loadRecallView").answer(recallView()));

    it("fall back to the defaults when nothing is remembered", async () => {
      stubStorage();

      await open();

      expect(view.getSnapshot().filters).toEqual(DEFAULTS);
    });

    it("fall back to the defaults when what is remembered is not readable", async () => {
      stubStorage({ [STORAGE_KEY]: "{not json" });

      await open();

      expect(view.getSnapshot().filters).toEqual(DEFAULTS);
    });

    it("fall back to the default for each invalid filter, keeping the valid ones", async () => {
      stubStorage({
        [STORAGE_KEY]: JSON.stringify({
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
    const withStudies = (studies) => ({ ...DEFAULTS, studies });

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
      expect(JSON.parse(remembered.get(STORAGE_KEY)).studies).toEqual(["italian"]);
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
      expect(shownKeys()).toEqual(["a"]);
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
      expect(shownKeys()).toEqual(["a", "new"]);
    });

    it("does not reload the view when it changed nothing", async () => {
      backend.on("loadRecallView").answer(recallView());
      await open();

      await finishSync(UNCHANGED);

      expect(backend.count("loadRecallView")).toBe(1);
    });
  });

  describe("a Sync during practice", () => {
    const FIRST = { games_changed: true, repertoire_changed: false, new_games: 2 };

    it("does not reload the view, and the \"what changed\" line stays the one of the analysis on screen", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();
      await finishSync(FIRST);
      expect(view.getSnapshot().syncResult).toEqual(FIRST);

      view.startDrill();
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("new")] }));
      await finishSync(CHANGED);

      expect(backend.count("loadRecallView")).toBe(2);
      expect(shownKeys()).toEqual(["a"]);
      expect(view.getSnapshot().syncResult).toEqual(FIRST);
    });

    it("is applied, with its \"what changed\" line, when practice ends", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      view.startSession();
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("new")] }));
      await finishSync(CHANGED);
      expect(view.getSnapshot().syncResult).toBeNull();

      view.endPractice();
      expect(view.getSnapshot().practice).toBeNull();
      expect(view.getSnapshot().syncResult).toEqual(CHANGED);
      await settle();
      expect(shownKeys()).toEqual(["a", "new"]);
    });

    it("shows its \"what changed\" line when practice ends, without a reload, if it changed nothing", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      view.startDrill();
      await finishSync(UNCHANGED);
      expect(view.getSnapshot().syncResult).toBeNull();

      view.endPractice();
      await settle();
      expect(view.getSnapshot().syncResult).toEqual(UNCHANGED);
      expect(backend.count("loadRecallView")).toBe(1);
    });

    it("keeps the selected Recall Gap across the held analysis when it still exists", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.toggleClosed();
      view.selectGap("b");

      view.startSession();
      backend
        .on("loadRecallView")
        .answer(recallView({ gaps: [gap("new"), gap("a"), gap("b", "closed")] }));
      await finishSync(CHANGED);
      view.endPractice();
      await settle();

      expect(view.getSnapshot().selected.position_key).toBe("b");
    });

    it("keeps the first shown gap selected across the held analysis when none was picked", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();

      view.startSession();
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("new"), gap("a"), gap("b")] }));
      await finishSync(CHANGED);
      view.endPractice();
      await settle();

      expect(view.getSnapshot().selected.position_key).toBe("a");
    });
  });

  describe("a load in flight when practice starts", () => {
    it("never updates the view, and is run again when practice ends", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();
      backend.on("loadRecallView").delay(500).answer(recallView({ gaps: [gap("b")] }));
      view.setFilters({ ...view.getSnapshot().filters, dateRange: "year" });

      view.startDrill();
      expect(view.getSnapshot().loading).toBe(false);
      await vi.advanceTimersByTimeAsync(500);
      expect(shownKeys()).toEqual(["a"]);

      view.endPractice();
      expect(view.getSnapshot().loading).toBe(true);
      await vi.advanceTimersByTimeAsync(500);
      expect(backend.count("loadRecallView")).toBe(3);
      expect(shownKeys()).toEqual(["b"]);
    });

    it("is not run again when practice ends if none was in flight", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a")] }));
      await open();

      view.startDrill();
      view.endPractice();
      await settle();

      expect(backend.count("loadRecallView")).toBe(1);
    });
  });

  describe("a single drill", () => {
    it("is of the selected Recall Gap", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.selectGap("b");

      view.startDrill();

      expect(view.getSnapshot().practice.gap.position_key).toBe("b");
    });

    it("keeps its Recall Gap when the gap is no longer the selected one", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b", "closed")] }));
      await open();
      view.toggleClosed();
      view.selectGap("b");
      view.startDrill();

      view.toggleClosed();

      expect(view.getSnapshot().selected.position_key).toBe("a");
      expect(view.getSnapshot().practice.gap.position_key).toBe("b");
    });

    it("does not start when no Recall Gap is shown", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [] }));
      await open();

      view.startDrill();

      expect(view.getSnapshot().practice).toBeNull();
    });

    it("ends when another Recall Gap is selected", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.startDrill();

      view.selectGap("b");

      expect(view.getSnapshot().practice).toBeNull();
      expect(view.getSnapshot().selected.position_key).toBe("b");
    });

    it("goes on when its own Recall Gap is selected again", async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.startDrill();

      view.selectGap("a");

      expect(view.getSnapshot().practice.kind).toBe("drill");
    });
  });

  const PASS = { gap_position_key: "a", passed: true, first_miss_position_key: null };
  const FAIL = { gap_position_key: "a", passed: false, first_miss_position_key: "miss" };

  describe("a finished drill", () => {
    beforeEach(async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b")] }));
      await open();
      view.startDrill();
    });

    it("records its Drill Attempt, showing saving and then saved", async () => {
      backend.on("recordDrillAttempt").delay(200).answer({});
      expect(view.getSnapshot().practice.saveState).toBeNull();

      view.finishDrill(FAIL);
      expect(view.getSnapshot().practice.saveState).toBe("saving");
      await vi.advanceTimersByTimeAsync(200);

      expect(view.getSnapshot().practice.saveState).toBe("saved");
      expect(backend.calls("recordDrillAttempt")).toEqual([[FAIL]]);
    });

    it("records exactly one Drill Attempt, even if reported more than once", async () => {
      backend.on("recordDrillAttempt").delay(200).answer({});

      view.finishDrill(PASS);
      view.finishDrill(PASS);
      await vi.advanceTimersByTimeAsync(200);
      view.finishDrill(PASS);
      await settle();

      expect(backend.count("recordDrillAttempt")).toBe(1);
      expect(view.getSnapshot().practice.saveState).toBe("saved");
    });

    it("shows a failed save as failed, and saves the same Drill Attempt on retry", async () => {
      backend.on("recordDrillAttempt").fail("Server error");
      view.finishDrill(FAIL);
      await settle();
      expect(view.getSnapshot().practice.saveState).toBe("failed");

      backend.on("recordDrillAttempt").delay(200).answer({});
      view.retrySave();
      expect(view.getSnapshot().practice.saveState).toBe("saving");
      await vi.advanceTimersByTimeAsync(200);

      expect(view.getSnapshot().practice.saveState).toBe("saved");
      expect(backend.calls("recordDrillAttempt")).toEqual([[FAIL], [FAIL]]);
    });

    it("is not saved again by a retry once it is saved", async () => {
      backend.on("recordDrillAttempt").answer({});
      view.finishDrill(PASS);
      await settle();

      view.retrySave();
      await settle();

      expect(backend.count("recordDrillAttempt")).toBe(1);
    });

    it("can be drilled again: a new drill of the same gap that records its own Drill Attempt", async () => {
      backend.on("recordDrillAttempt").answer({});
      view.finishDrill(FAIL);
      await settle();
      const first = view.getSnapshot().practice;

      view.drillAgain();
      const again = view.getSnapshot().practice;
      expect(again).toMatchObject({ kind: "drill", gap: first.gap, saveState: null });
      expect(again.drillNumber).not.toBe(first.drillNumber);

      view.finishDrill(PASS);
      await settle();
      expect(backend.calls("recordDrillAttempt")).toEqual([[FAIL], [PASS]]);
      expect(view.getSnapshot().practice.saveState).toBe("saved");
    });

    it("leaves the next drill alone when its save answers after \"Drill again\"", async () => {
      backend.on("recordDrillAttempt").delay(200).fail("Server error");
      view.finishDrill(FAIL);

      view.drillAgain();
      await vi.advanceTimersByTimeAsync(200);

      expect(view.getSnapshot().practice.saveState).toBeNull();
    });

    it("leaves the view alone when its save answers after practice ended", async () => {
      backend.on("recordDrillAttempt").delay(200).answer({});
      view.finishDrill(PASS);

      view.endPractice();
      await vi.advanceTimersByTimeAsync(200);

      expect(view.getSnapshot().practice).toBeNull();
    });
  });

  describe("a practice session", () => {
    const YEAR = { ...DEFAULTS, dateRange: "year" };

    /** Finish the drill on the board and let its Drill Attempt be saved. */
    async function finishAndSave() {
      view.finishDrill({ ...PASS, gap_position_key: view.getSnapshot().practice.gap.position_key });
      await settle();
    }

    beforeEach(async () => {
      backend.on("loadRecallView").answer(recallView({ gaps: [gap("a"), gap("b"), gap("c")] }));
      backend.on("recordDrillAttempt").answer({});
      await open();
    });

    it("drills the first Recall Gap of its queue once the queue is loaded", async () => {
      backend.on("loadPracticeQueue").delay(300).answer([gap("b"), gap("c")]);

      view.startSession();
      expect(view.getSnapshot().practice).toMatchObject({
        kind: "session",
        queue: null,
        error: null,
        drilled: 0,
      });
      expect(view.getSnapshot().practice.gap).toBeUndefined();
      await vi.advanceTimersByTimeAsync(300);

      expect(view.getSnapshot().practice).toMatchObject({
        queue: [gap("b"), gap("c")],
        index: 0,
        gap: gap("b"),
        saveState: null,
      });
    });

    it("fetches its queue under the Game Filters, each time it fetches it", async () => {
      backend.on("loadPracticeQueue").answer([gap("a")]);
      view.setFilters(YEAR);
      await settle();
      view.startSession();
      await settle();

      await finishAndSave();
      view.nextDrill();
      await settle();

      expect(backend.calls("loadPracticeQueue")).toEqual([[YEAR], [YEAR]]);
    });

    it("advances to the next Recall Gap only after the Drill Attempt is saved", async () => {
      backend.on("loadPracticeQueue").answer([gap("a"), gap("b")]);
      backend.on("recordDrillAttempt").delay(200).answer({});
      view.startSession();
      await settle();
      const first = view.getSnapshot().practice.drillNumber;

      view.nextDrill();
      expect(view.getSnapshot().practice.index).toBe(0);
      view.finishDrill(PASS);
      view.nextDrill();
      expect(view.getSnapshot().practice.index).toBe(0);

      await vi.advanceTimersByTimeAsync(200);
      view.nextDrill();
      expect(view.getSnapshot().practice).toMatchObject({
        index: 1,
        gap: gap("b"),
        drilled: 1,
        saveState: null,
      });
      expect(view.getSnapshot().practice.drillNumber).not.toBe(first);
      expect(backend.count("loadPracticeQueue")).toBe(1);
    });

    it("does not advance while the Drill Attempt's save has failed", async () => {
      backend.on("loadPracticeQueue").answer([gap("a"), gap("b")]);
      backend.on("recordDrillAttempt").fail("Server error");
      view.startSession();
      await settle();

      view.finishDrill(PASS);
      await settle();
      view.nextDrill();

      expect(view.getSnapshot().practice).toMatchObject({ index: 0, drilled: 0, saveState: "failed" });
    });

    it("records one Drill Attempt for each drill of the queue", async () => {
      backend.on("loadPracticeQueue").answer([gap("a"), gap("b")]);
      view.startSession();
      await settle();

      await finishAndSave();
      view.nextDrill();
      await finishAndSave();

      expect(backend.calls("recordDrillAttempt").map(([attempt]) => attempt.gap_position_key)).toEqual([
        "a",
        "b",
      ]);
    });

    it("fetches the queue again when it runs out, so gaps failed on the way come back", async () => {
      backend.on("loadPracticeQueue").answer([gap("a"), gap("b")]);
      view.startSession();
      await settle();
      await finishAndSave();
      view.nextDrill();
      await finishAndSave();
      const last = view.getSnapshot().practice.drillNumber;

      backend.on("loadPracticeQueue").answer([gap("b")]);
      view.nextDrill();
      await settle();

      expect(backend.count("loadPracticeQueue")).toBe(2);
      expect(view.getSnapshot().practice).toMatchObject({
        queue: [gap("b")],
        index: 0,
        gap: gap("b"),
        drilled: 2,
        saveState: null,
      });
      expect(view.getSnapshot().practice.drillNumber).not.toBe(last);
    });

    it("reports nothing due, and how many gaps were drilled, when the queue comes back empty", async () => {
      backend.on("loadPracticeQueue").answer([gap("a")]);
      view.startSession();
      await settle();
      await finishAndSave();

      backend.on("loadPracticeQueue").answer([]);
      view.nextDrill();
      await settle();

      expect(view.getSnapshot().practice).toMatchObject({ queue: [], drilled: 1, error: null });
      expect(view.getSnapshot().practice.gap).toBeUndefined();
    });

    it("reports nothing due at once when nothing is due at its start", async () => {
      backend.on("loadPracticeQueue").answer([]);

      view.startSession();
      await settle();

      expect(view.getSnapshot().practice).toMatchObject({ queue: [], drilled: 0 });
      expect(view.getSnapshot().practice.gap).toBeUndefined();
    });

    it("shows why its queue failed to load, and loads it on retry", async () => {
      backend.on("loadPracticeQueue").fail("Could not load the practice session");
      view.startSession();
      await settle();
      expect(view.getSnapshot().practice).toMatchObject({
        error: "Could not load the practice session",
        queue: null,
      });

      backend.on("loadPracticeQueue").delay(300).answer([gap("a")]);
      view.retryQueue();
      expect(view.getSnapshot().practice.error).toBeNull();
      await vi.advanceTimersByTimeAsync(300);

      expect(view.getSnapshot().practice).toMatchObject({ error: null, gap: gap("a") });
      expect(backend.count("loadPracticeQueue")).toBe(2);
    });

    it("counts the last gap of its queue once, however often \"Next\" is asked before the queue arrives", async () => {
      backend.on("loadPracticeQueue").answer([gap("a")]);
      view.startSession();
      await settle();
      await finishAndSave();

      backend.on("loadPracticeQueue").delay(300).answer([]);
      view.nextDrill();
      view.nextDrill();
      view.nextDrill();
      await vi.advanceTimersByTimeAsync(300);

      expect(view.getSnapshot().practice.drilled).toBe(1);
      expect(backend.count("loadPracticeQueue")).toBe(2);
    });

    it("has no Recall Gap to drill while its queue is fetched again", async () => {
      backend.on("loadPracticeQueue").answer([gap("a")]);
      view.startSession();
      await settle();
      await finishAndSave();

      backend.on("loadPracticeQueue").delay(300).answer([gap("a")]);
      view.nextDrill();

      expect(view.getSnapshot().practice).toMatchObject({ queue: null, error: null, drilled: 1 });
      expect(view.getSnapshot().practice.gap).toBeUndefined();
    });

    it("has no Recall Gap to drill after its queue failed to load again, nor during the retry", async () => {
      backend.on("loadPracticeQueue").answer([gap("a")]);
      view.startSession();
      await settle();
      await finishAndSave();

      backend.on("loadPracticeQueue").fail("Could not load the practice session");
      view.nextDrill();
      await settle();
      expect(view.getSnapshot().practice).toMatchObject({
        error: "Could not load the practice session",
        queue: null,
      });
      expect(view.getSnapshot().practice.gap).toBeUndefined();

      backend.on("loadPracticeQueue").delay(300).answer([gap("b")]);
      view.retryQueue();
      expect(view.getSnapshot().practice).toMatchObject({ error: null, queue: null });
      expect(view.getSnapshot().practice.gap).toBeUndefined();
      await vi.advanceTimersByTimeAsync(300);

      expect(view.getSnapshot().practice).toMatchObject({ gap: gap("b"), drilled: 1, saveState: null });
      await finishAndSave();
      expect(backend.calls("recordDrillAttempt").map(([attempt]) => attempt.gap_position_key)).toEqual([
        "a",
        "b",
      ]);
    });

    it("records no second Drill Attempt for the last gap of the queue that ran out", async () => {
      backend.on("loadPracticeQueue").answer([gap("a")]);
      view.startSession();
      await settle();
      await finishAndSave();

      backend.on("loadPracticeQueue").fail("Could not load the practice session");
      view.nextDrill();
      view.finishDrill(PASS);
      await settle();
      view.finishDrill(PASS);
      backend.on("loadPracticeQueue").delay(300).fail("Could not load the practice session");
      view.retryQueue();
      view.finishDrill(PASS);
      await vi.advanceTimersByTimeAsync(300);
      view.finishDrill(PASS);
      await settle();

      expect(backend.count("recordDrillAttempt")).toBe(1);
    });

    it("records no Drill Attempt while it has no Recall Gap to drill", async () => {
      backend.on("loadPracticeQueue").delay(300).answer([]);
      view.startSession();
      view.finishDrill(PASS);
      await vi.advanceTimersByTimeAsync(300);
      view.finishDrill(PASS);
      await settle();

      expect(backend.count("recordDrillAttempt")).toBe(0);
    });

    it("can be stopped when its queue failed to load", async () => {
      backend.on("loadPracticeQueue").fail("Could not load the practice session");
      view.startSession();
      await settle();

      view.endPractice();

      expect(view.getSnapshot().practice).toBeNull();
    });

    it("leaves the view alone when its queue answers after it was stopped", async () => {
      backend.on("loadPracticeQueue").delay(300).answer([gap("a")]);
      view.startSession();

      view.endPractice();
      await vi.advanceTimersByTimeAsync(300);

      expect(view.getSnapshot().practice).toBeNull();
    });

    it("goes on when a Recall Gap is selected in the list", async () => {
      backend.on("loadPracticeQueue").answer([gap("a"), gap("b")]);
      view.startSession();
      await settle();

      view.selectGap("c");

      expect(view.getSnapshot().practice).toMatchObject({ kind: "session", gap: gap("a") });
    });

    it("takes over from a single drill", async () => {
      backend.on("loadPracticeQueue").answer([gap("b")]);
      view.startDrill();

      view.startSession();
      await settle();

      expect(view.getSnapshot().practice).toMatchObject({ kind: "session", gap: gap("b") });
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
      expect(shownKeys()).toEqual(["a", "c"]);
      expect(view.getSnapshot().closedCount).toBe(2);
    });

    it("are shown in ranking order once toggled on, and hidden again when toggled off", async () => {
      await open();

      view.toggleClosed();
      expect(view.getSnapshot().showClosed).toBe(true);
      expect(shownKeys()).toEqual(["a", "b", "c", "d"]);

      view.toggleClosed();
      expect(shownKeys()).toEqual(["a", "c"]);
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
