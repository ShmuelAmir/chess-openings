import { useState, useLayoutEffect, useSyncExternalStore } from "react";
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

  // Before the first paint, so the page never shows empty
  useLayoutEffect(() => {
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
  const { syncStatus, syncing, syncError, startSync } = useSync();
  const {
    filters,
    view,
    loading,
    error,
    showClosed,
    shownGaps,
    closedCount,
    selected,
    practice,
    syncResult,
  } = useSyncExternalStore(recallView.subscribe, recallView.getSnapshot);

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
            onSelect={recallView.selectGap}
            loading={loading}
            syncing={syncing}
            syncResult={syncResult}
            practicing={practice?.kind === "session"}
            onPractice={recallView.startSession}
          />
        )}
      </section>

      {practice?.kind === "session" ? (
        <PracticeSession
          session={practice}
          onFinished={recallView.finishDrill}
          onRetrySave={recallView.retrySave}
          onNext={recallView.nextDrill}
          onRetryQueue={recallView.retryQueue}
          onEnd={recallView.endPractice}
        />
      ) : practice?.kind === "drill" ? (
        // The drill hides the gap's details, which would give the answer away
        <section className="rv-detail">
          <DrillBoard
            key={practice.drillNumber}
            gap={practice.gap}
            boardWidth={BOARD_WIDTH}
            saveState={practice.saveState}
            onFinished={recallView.finishDrill}
            onRetrySave={recallView.retrySave}
            onAgain={recallView.drillAgain}
            onClose={recallView.endPractice}
          />
        </section>
      ) : (
        <GapDetail
          key={selected?.position_key}
          gap={selected}
          onDrill={recallView.startDrill}
        />
      )}
    </div>
  );
}
