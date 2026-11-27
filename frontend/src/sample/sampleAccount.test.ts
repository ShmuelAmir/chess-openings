import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createSyncClient, type SyncClient } from "../sync/syncClient";
import {
  createRecallView,
  type RecallViewSnapshot,
  type RecallViewStore,
} from "../recall/recallView";
import { createSampleAccount } from "./sampleAccount";
import { Chess } from "chess.js";
import {
  drillAttempt,
  drillFen,
  playOpponent,
  playUserMove,
  startDrill,
  userTurn,
  type DrillState as Drill,
} from "../components/recall/drill";
import type {
  DrillAttempt,
  GameFilters,
  RecallGap,
  RecallView,
} from "../backend/backend";

const NOW = new Date("2026-10-09T12:00:00Z");
const ALL_GAMES: GameFilters = {
  timeClasses: [],
  dateRange: "all",
  ratedOnly: false,
  studies: [],
};

/** Let the sample backend's answers reach the recall view. */
const settle = () => vi.advanceTimersByTimeAsync(0);

describe("sample account", () => {
  let syncClient: SyncClient;
  let view: RecallViewStore;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    view?.dispose();
    syncClient?.dispose();
    vi.useRealTimers();
  });

  async function open() {
    const { backend } = createSampleAccount();
    syncClient = createSyncClient(backend);
    view = createRecallView({ backend, syncClient });
    view.setFilters(ALL_GAMES);
    await settle();
    return view.getSnapshot();
  }

  /** The practice session in progress. */
  function session() {
    const { practice } = view.getSnapshot();
    if (practice?.kind !== "session") throw new Error("No practice session");
    return practice;
  }

  it("opens the recall view on Studies of both colors, ranked gaps and a year of trend", async () => {
    const snapshot = await open();
    const { shownGaps, closedCount, error } = snapshot;
    const recall = loaded(snapshot);

    expect(error).toBeNull();
    expect(new Set(recall.studies.map((study) => study.color))).toEqual(
      new Set(["white", "black"]),
    );
    expect(shownGaps.length).toBeGreaterThan(3);
    expect(closedCount).toBeGreaterThan(0);
    const occurrences = shownGaps.map((gap) => gap.occurrences);
    expect(occurrences).toEqual([...occurrences].sort((a, b) => b - a));
    expect(recall.totals.trend).toHaveLength(12);
    expect(
      recall.totals.trend.every((month) => month.miss_depths.length === 9),
    ).toBe(true);
  });

  it("narrows the gaps and the totals to the selected Study", async () => {
    const all = await open();
    view.setFilters({ ...ALL_GAMES, studies: ["sNajdorf"] });
    await settle();
    const { shownGaps } = view.getSnapshot();
    const najdorf = loaded(view.getSnapshot());

    expect(shownGaps.length).toBeGreaterThan(0);
    expect(shownGaps.length).toBeLessThan(all.shownGaps.length);
    expect(
      shownGaps.every((gap) =>
        gap.studies.some((study) => study.id === "sNajdorf"),
      ),
    ).toBe(true);
    expect(najdorf.totals.analysed).toBeLessThan(loaded(all).totals.analysed);
    // The Study filter never changes the list of Studies
    expect(najdorf.studies).toEqual(loaded(all).studies);
  });

  it("practises the due gaps, and a passed drill is not due again", async () => {
    await open();
    view.startSession();
    await settle();
    const first = session().gap;
    if (!first) throw new Error("Nothing is due");
    expect(first.status).toBe("open");

    view.finishDrill(playDrill(first));
    await settle();
    expect(session().saveState).toBe("saved");

    view.endPractice();
    view.startSession();
    await settle();
    const { queue } = session();
    if (!queue) throw new Error("The practice queue has not loaded");
    expect(queue.length).toBeGreaterThan(0);
    expect(queue.map((gap) => gap.position_key)).not.toContain(
      first.position_key,
    );
  });

  it("has a playable drill for every gap, wrong moves included", async () => {
    await open();
    view.toggleClosed();
    const { shownGaps } = view.getSnapshot();

    for (const gap of shownGaps) {
      expect(playDrill(gap)).toEqual({
        gap_position_key: gap.position_key,
        passed: true,
        first_miss_position_key: null,
      });
      // Each wrong move is legal at the gap, and not a Book move
      const wrong = drillAt(gap);
      for (const { san } of gap.wrong_moves) {
        const failed = playUserMove(wrong, moveOf(wrong, san));
        expect(failed?.wrongMove).toBe(san);
      }
    }
  });
});

/** The Recall view the backend reported, which these tests wait for. */
function loaded(snapshot: RecallViewSnapshot): RecallView {
  if (!snapshot.view) throw new Error("The recall view has not loaded");
  return snapshot.view;
}

/** The board move of a SAN move in the drill's current position. */
function moveOf(drill: Drill, san: string) {
  const { from, to, promotion } = new Chess(drillFen(drill)).move(san);
  return { from, to, promotion };
}

/** The user plays a SAN move, which must be legal here. */
function playUser(drill: Drill, san: string): Drill {
  const next = playUserMove(drill, moveOf(drill, san));
  if (!next) throw new Error(`${san} is illegal here`);
  return next;
}

/** The drill of `gap`, played along its path up to the gap itself. */
function drillAt(gap: RecallGap): Drill {
  let drill = startDrill(gap);
  while (drill.ply < drill.gapPly) {
    drill = userTurn(drill)
      ? playUser(drill, drill.path[drill.ply])
      : playOpponent(drill);
  }
  return drill;
}

/** The Drill Attempt of `gap` played without a wrong move. */
function playDrill(gap: RecallGap): DrillAttempt {
  const drill = drillAt(gap);
  return drillAttempt(playUser(drill, gap.book_moves[0]));
}
