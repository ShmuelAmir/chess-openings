import { useState, useEffect, useCallback, useSyncExternalStore } from "react";
import { useAuth } from "../context/AuthContext";
import { useSync } from "../context/SyncContext";
import { createRecallView } from "../recall/recallView";
import FilterRail from "../components/recall/FilterRail";
import GapList from "../components/recall/GapList";
import GapDetail from "../components/recall/GapDetail";
import DrillBoard from "../components/recall/DrillBoard";
import PracticeSession from "../components/recall/PracticeSession";
import SyncBar from "../components/recall/SyncBar";
import "../components/recall/recall.css";

const BOARD_WIDTH = 306;

/** Keeps one recall view while the page is open, for the account's Sync client. */
export default function RecallPage() {
  const { backend, syncClient } = useSync();
  const [recallView, setRecallView] = useState(null);

  useEffect(() => {
    if (!syncClient) return;
    const created = createRecallView({ backend, syncClient });
    setRecallView(created);
    return () => {
      created.dispose();
      setRecallView(null);
    };
  }, [backend, syncClient]);

  return recallView && <Recall recallView={recallView} />;
}

function Recall({ recallView }) {
  const { lichessToken, chessComUsername } = useAuth();
  const { syncStatus, syncing, syncError, syncResult, startSync } = useSync();
  const { filters, view, loading, error, showClosed, shownGaps, closedCount, selected } =
    useSyncExternalStore(recallView.subscribe, recallView.getSnapshot);

  // The practice in progress: null, { kind: "session" }, or { kind: "drill",
  // gap } with the gap as it was when the drill started, so a held Sync
  // never changes the board
  const [practice, setPractice] = useState(null);

  // The "what changed" line is held with the analysis it describes
  const [shownSyncResult, setShownSyncResult] = useState(syncResult);
  useEffect(() => {
    if (!practice) setShownSyncResult(syncResult);
  }, [practice, syncResult]);

  // A Sync that finishes while practising is held, so the board never
  // changes under the user, and applied once practice ends
  const startPractice = (started) => {
    recallView.hold();
    // Keep the selected gap across the held analysis, if it still exists
    if (selected) recallView.selectGap(selected.position_key);
    setPractice(started);
  };

  const endPractice = () => {
    setPractice(null);
    recallView.release();
  };

  // Selecting another gap ends a drill of the previous one
  const selectGap = (key) => {
    if (practice?.kind === "drill" && key !== practice.gap.position_key) endPractice();
    recallView.selectGap(key);
  };

  const fetchPracticeQueue = useCallback(async () => {
    const params = new URLSearchParams({
      chess_com_username: chessComUsername,
      date_range: filters.dateRange,
      rated_only: filters.ratedOnly,
    });
    filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
    filters.studies.forEach((id) => params.append("studies", id));
    const response = await fetch(`/api/practice-session?${params}`, {
      headers: { Authorization: `Bearer ${lichessToken}` },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Could not load the practice session");
    }
    return (await response.json()).gaps;
  }, [chessComUsername, filters, lichessToken]);

  return (
    <div className="rv">
      <FilterRail
        filters={filters}
        studies={view?.studies ?? []}
        onChange={recallView.setFilters}
      />

      <section className="rv-list">
        <SyncBar
          status={syncStatus}
          syncing={syncing}
          error={syncError}
          onSync={startSync}
        />

        {error && <div className="error">{error}</div>}

        {syncStatus && !syncStatus.cached_games ? (
          <div className="empty-state">
            <p>
              {syncing
                ? (syncStatus.progress ?? "Syncing…")
                : 'Click "Sync" to fetch your Chess.com games'}
            </p>
          </div>
        ) : !view ? (
          <div className="loading">Loading Recall Gaps...</div>
        ) : (
          <GapList
            gaps={shownGaps}
            closedCount={closedCount}
            showClosed={showClosed}
            onToggleClosed={recallView.toggleClosed}
            totals={view.totals}
            selectedKey={selected?.position_key}
            onSelect={selectGap}
            loading={loading}
            syncing={syncing}
            syncResult={shownSyncResult}
            practicing={practice?.kind === "session"}
            onPractice={() => startPractice({ kind: "session" })}
          />
        )}
      </section>

      {practice?.kind === "session" ? (
        <PracticeSession fetchQueue={fetchPracticeQueue} onEnd={endPractice} />
      ) : practice?.kind === "drill" ? (
        // The drill hides the gap's details, which would give the answer away
        <section className="rv-detail">
          <DrillBoard gap={practice.gap} boardWidth={BOARD_WIDTH} onClose={endPractice} />
        </section>
      ) : (
        <GapDetail
          key={selected?.position_key}
          gap={selected}
          onDrill={() => startPractice({ kind: "drill", gap: selected })}
        />
      )}
    </div>
  );
}
