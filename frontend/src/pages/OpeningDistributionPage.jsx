import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import GameFilters from "../components/GameFilters";
import OpeningCharts from "../components/OpeningCharts";

export default function OpeningDistributionPage() {
  const { chessComUsername, cacheStatus } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeFilters, setActiveFilters] = useState(null);

  const loadStats = useCallback(
    async (filters = null) => {
      if (!chessComUsername) return;

      setLoading(true);
      setError(null);

      try {
        const currentDate = new Date();
        const nowTs = Math.floor(Date.now() / 1000);
        const weekAgoTs = nowTs - 7 * 24 * 60 * 60;
        const weekAgoDate = new Date(weekAgoTs * 1000);
        const defaultFilters = filters ||
          activeFilters || {
            fromYear: weekAgoDate.getFullYear(),
            fromMonth: weekAgoDate.getMonth() + 1,
            toYear: currentDate.getFullYear(),
            toMonth: currentDate.getMonth() + 1,
            fromTimestamp: weekAgoTs,
            toTimestamp: nowTs,
            timeClasses: ["rapid"],
            colorFilter: "both",
            ratedOnly: true,
          };

        const params = new URLSearchParams({
          chess_com_username: chessComUsername,
          from_year: defaultFilters.fromYear,
          from_month: defaultFilters.fromMonth,
          to_year: defaultFilters.toYear,
          to_month: defaultFilters.toMonth,
        });

        if (defaultFilters.fromTimestamp) {
          params.append("from_ts", defaultFilters.fromTimestamp);
        }
        if (defaultFilters.toTimestamp) {
          params.append("to_ts", defaultFilters.toTimestamp);
        }

        if (
          defaultFilters.timeClasses &&
          defaultFilters.timeClasses.length > 0
        ) {
          defaultFilters.timeClasses.forEach((tc) =>
            params.append("time_classes", tc),
          );
        }
        if (defaultFilters.ratedOnly) {
          params.append("rated", "true");
        }
        if (
          defaultFilters.colorFilter &&
          defaultFilters.colorFilter !== "both"
        ) {
          params.append("color", defaultFilters.colorFilter);
        }

        const response = await fetch(`/api/opening-stats?${params}`, {
          method: "POST",
        });

        if (!response.ok) {
          throw new Error("Failed to fetch opening statistics");
        }

        const result = await response.json();
        setData(result);
        setActiveFilters(defaultFilters);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [chessComUsername, activeFilters],
  );

  // Auto-load on mount when there are cached games
  useEffect(() => {
    if (cacheStatus?.cached_games > 0 && !data && !loading) {
      loadStats();
    }
  }, [cacheStatus]);

  const handleApplyFilters = (filters) => {
    loadStats(filters);
  };

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div className="main-layout opening-layout">
        <div className="setup-panel opening-filters">
          <div className="section">
            <h2>Filters</h2>
            <GameFilters
              onAnalyze={handleApplyFilters}
              loading={loading}
              showUsernameField={false}
              buttonText="Apply Filters"
            />
          </div>
        </div>

        <div className="results-panel opening-results">
          {!cacheStatus?.cached_games && (
            <div className="empty-state">
              <p>Sync your Chess.com games first to see opening statistics</p>
            </div>
          )}

          {loading && (
            <div className="section">
              <div className="loading">Fetching opening statistics...</div>
            </div>
          )}

          {!loading && data && (
            <div className="section">
              <OpeningCharts data={data} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
