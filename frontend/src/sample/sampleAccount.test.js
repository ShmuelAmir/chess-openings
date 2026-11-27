import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createSyncClient } from "../sync/syncClient";
import { createRecallView } from "../recall/recallView";
import { createSampleAccount } from "./sampleAccount";
import { Chess } from "chess.js";
import {
  drillAttempt,
  drillFen,
  playOpponent,
  playUserMove,
  startDrill,
  userTurn,
} from "../components/recall/drill";

const NOW = new Date("2026-10-09T12:00:00Z");
const ALL_GAMES = {
  timeClasses: [],
  dateRange: "all",
  ratedOnly: false,
  studies: [],
};

/** Let the sample backend's answers reach the recall view. */
const settle = () => vi.advanceTimersByTimeAsync(0);

describe("sample account", () => {
  let syncClient;
  let view;

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

  it("opens the recall view on Studies of both colors, ranked gaps and a year of trend", async () => {
    const { view: recall, shownGaps, closedCount, error } = await open();

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
    const { view: najdorf, shownGaps } = view.getSnapshot();

    expect(shownGaps.length).toBeGreaterThan(0);
    expect(shownGaps.length).toBeLessThan(all.shownGaps.length);
    expect(
      shownGaps.every((gap) =>
        gap.studies.some((study) => study.id === "sNajdorf"),
      ),
    ).toBe(true);
    expect(najdorf.totals.analysed).toBeLessThan(all.view.totals.analysed);
    // The Study filter never changes the list of Studies
    expect(najdorf.studies).toEqual(all.view.studies);
  });

  it("practises the due gaps, and a passed drill is not due again", async () => {
    await open();
    view.startSession();
    await settle();
    const first = view.getSnapshot().practice.gap;
    expect(first.status).toBe("open");

    view.finishDrill(playDrill(first));
    await settle();
    expect(view.getSnapshot().practice.saveState).toBe("saved");

    view.endPractice();
    view.startSession();
    await settle();
    const queue = view.getSnapshot().practice.queue;
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

/** The board move of a SAN move in the drill's current position. */
function moveOf(drill, san) {
  const { from, to, promotion } = new Chess(drillFen(drill)).move(san);
  return { from, to, promotion };
}

/** The drill of `gap`, played along its path up to the gap itself. */
function drillAt(gap) {
  let drill = startDrill(gap);
  while (drill.ply < drill.gapPly) {
    drill = userTurn(drill)
      ? playUserMove(drill, moveOf(drill, drill.path[drill.ply]))
      : playOpponent(drill);
  }
  return drill;
}

/** The Drill Attempt of `gap` played without a wrong move. */
function playDrill(gap) {
  const drill = drillAt(gap);
  return drillAttempt(playUserMove(drill, moveOf(drill, gap.book_moves[0])));
}
