import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { syncOrchestrator } from "../context/SyncOrchestrator";
import FilterRail from "../components/recall/FilterRail";
import GapList from "../components/recall/GapList";
import GapDetail from "../components/recall/GapDetail";
import PracticeSession from "../components/recall/PracticeSession";
import SyncBar from "../components/recall/SyncBar";
import { loadFilters, saveFilters } from "../components/recall/storedFilters";
import "../components/recall/recall.css";

export default function RecallPage() {
  const {
    lichessToken,
    chessComUsername,
    syncStatus,
    syncing,
    syncError,
    syncResult,
    startSync,
  } = useAuth();

  const [filters, setFilters] = useState(loadFilters);
  const [view, setView] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [showClosed, setShowClosed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [practicing, setPracticing] = useState(false);

  useEffect(() => saveFilters(filters), [filters]);

  // The Game Filters as query parameters, shared by the view and sessions
  const filterParams = useCallback(() => {
    const params = new URLSearchParams({
      chess_com_username: chessComUsername,
      date_range: filters.dateRange,
      rated_only: filters.ratedOnly,
    });
    filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
    filters.studies.forEach((id) => params.append("studies", id));
    return params;
  }, [chessComUsername, filters]);

  // Only the latest request may update the view
  const requestRef = useRef(0);

  const loadRecallView = useCallback(async () => {
    if (!chessComUsername || !lichessToken) return;
    const request = ++requestRef.current;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/recall-view?${filterParams()}`, {
        headers: { Authorization: `Bearer ${lichessToken}` },
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          response.status === 429
            ? "Lichess rate limit reached. Please wait a minute and try again."
            : data.detail || "Could not load Recall Gaps",
        );
      }

      const data = await response.json();
      if (request !== requestRef.current) return;
      // Forget selected studies that are no longer in the Repertoire (an
      // empty list says nothing about them, so keep the selection then)
      const known = new Set(data.studies.map((study) => study.id));
      if (known.size > 0 && filters.studies.some((id) => !known.has(id))) {
        setFilters({
          ...filters,
          studies: filters.studies.filter((id) => known.has(id)),
        });
        return;
      }
      setView(data);
    } catch (err) {
      if (request === requestRef.current) setError(err.message);
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  }, [chessComUsername, lichessToken, filters, filterParams]);

  useEffect(() => {
    loadRecallView();
  }, [loadRecallView]);

  // Re-load after a Sync brings in new games; a Sync that finishes while
  // practising is applied once practice ends
  const practicingRef = useRef(false);
  useEffect(() => {
    const onCacheReady = () => {
      if (!practicingRef.current) loadRecallView();
    };
    syncOrchestrator.on("cache-ready", onCacheReady);
    return () => syncOrchestrator.off("cache-ready", onCacheReady);
  }, [loadRecallView]);

  const startPractice = () => {
    practicingRef.current = true;
    setPracticing(true);
  };

  const endPractice = () => {
    practicingRef.current = false;
    setPracticing(false);
    // Apply any Sync that finished meanwhile
    loadRecallView();
  };

  const fetchPracticeQueue = useCallback(async () => {
    const response = await fetch(`/api/practice-session?${filterParams()}`, {
      headers: { Authorization: `Bearer ${lichessToken}` },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Could not load the practice session");
    }
    return (await response.json()).gaps;
  }, [filterParams, lichessToken]);

  const shownGaps = (view?.gaps ?? []).filter(
    (gap) => showClosed || gap.status === "open",
  );
  // The selected gap if it is still listed, else the first
  const selected =
    shownGaps.find((gap) => gap.position_key === selectedKey) ?? shownGaps[0];

  return (
    <div className="rv">
      <FilterRail
        filters={filters}
        studies={view?.studies ?? []}
        onChange={setFilters}
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
            closedCount={view.gaps.filter((gap) => gap.status === "closed").length}
            showClosed={showClosed}
            onToggleClosed={() => setShowClosed(!showClosed)}
            totals={view.totals}
            selectedKey={selected?.position_key}
            onSelect={setSelectedKey}
            loading={loading}
            syncing={syncing}
            syncResult={syncResult}
            practicing={practicing}
            onPractice={startPractice}
          />
        )}
      </section>

      {practicing ? (
        <PracticeSession fetchQueue={fetchPracticeQueue} onEnd={endPractice} />
      ) : (
        <GapDetail key={selected?.position_key} gap={selected} />
      )}
    </div>
  );
}
