import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { syncOrchestrator } from "../context/SyncOrchestrator";
import FilterRail from "../components/recall/FilterRail";
import GapList from "../components/recall/GapList";
import GapDetail from "../components/recall/GapDetail";
import { loadFilters, saveFilters } from "../components/recall/storedFilters";
import "../components/recall/recall.css";

export default function RecallPage() {
  const { lichessToken, chessComUsername, cacheStatus } = useAuth();

  const [filters, setFilters] = useState(loadFilters);
  const [view, setView] = useState(null);
  const [selectedKey, setSelectedKey] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => saveFilters(filters), [filters]);

  // Only the latest request may update the view
  const requestRef = useRef(0);

  const loadRecallView = useCallback(async () => {
    if (!chessComUsername || !lichessToken) return;
    const request = ++requestRef.current;

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        chess_com_username: chessComUsername,
        date_range: filters.dateRange,
        rated_only: filters.ratedOnly,
      });
      filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
      filters.studies.forEach((id) => params.append("studies", id));

      const response = await fetch(`/api/recall-view?${params}`, {
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
      // Keep the selected gap if it is still listed, else select the first
      setSelectedKey((key) =>
        data.gaps.some((gap) => gap.position_key === key)
          ? key
          : (data.gaps[0]?.position_key ?? null),
      );
    } catch (err) {
      if (request === requestRef.current) setError(err.message);
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  }, [chessComUsername, lichessToken, filters]);

  useEffect(() => {
    loadRecallView();
  }, [loadRecallView]);

  // Re-load after a Sync brings in new games
  useEffect(() => {
    syncOrchestrator.on("cache-ready", loadRecallView);
    return () => syncOrchestrator.off("cache-ready", loadRecallView);
  }, [loadRecallView]);

  const selected = view?.gaps.find((gap) => gap.position_key === selectedKey);

  return (
    <div className="rv">
      <FilterRail
        filters={filters}
        studies={view?.studies ?? []}
        onChange={setFilters}
      />

      <section className="rv-list">
        {error && <div className="error">{error}</div>}

        {cacheStatus && !cacheStatus.cached_games ? (
          <div className="empty-state">
            <p>Click "Sync" to fetch your Chess.com games</p>
          </div>
        ) : !view ? (
          <div className="loading">Loading Recall Gaps...</div>
        ) : (
          <GapList
            gaps={view.gaps}
            totals={view.totals}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
            loading={loading}
          />
        )}
      </section>

      <GapDetail gap={selected} />
    </div>
  );
}
