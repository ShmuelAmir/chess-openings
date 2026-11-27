import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { useSync } from "../context/SyncContext";
import GameFilters, {
  type OpeningDistributionFilters,
} from "../components/GameFilters";
import OpeningCharts, {
  type OpeningDistribution,
} from "../components/OpeningCharts";

export default function OpeningDistributionPage() {
  const { chessComUsername } = useAuth();
  const { cachedGames } = useSync();

  const [data, setData] = useState<OpeningDistribution | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFilters, setActiveFilters] =
    useState<OpeningDistributionFilters | null>(null);

  const loadStats = useCallback(
    async (filters: OpeningDistributionFilters | null = null) => {
      if (!chessComUsername) return;

      setLoading(true);
      setError(null);

      try {
        const currentDate = new Date();
        const nowTs = Math.floor(Date.now() / 1000);
        const weekAgoTs = nowTs - 7 * 24 * 60 * 60;
        const weekAgoDate = new Date(weekAgoTs * 1000);
        const defaultFilters: OpeningDistributionFilters = filters ||
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
          from_year: String(defaultFilters.fromYear),
          from_month: String(defaultFilters.fromMonth),
          to_year: String(defaultFilters.toYear),
          to_month: String(defaultFilters.toMonth),
        });

        if (defaultFilters.fromTimestamp) {
          params.append("from_ts", String(defaultFilters.fromTimestamp));
        }
        if (defaultFilters.toTimestamp) {
          params.append("to_ts", String(defaultFilters.toTimestamp));
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

        const result: OpeningDistribution = await response.json();
        setData(result);
        setActiveFilters(defaultFilters);
      } catch (err) {
        // fetch and response.json throw only Errors, and so does this block
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [chessComUsername, activeFilters],
  );

  // Auto-load on mount when there are cached games
  useEffect(() => {
    // cachedGames is null before the first Sync state arrives
    if (cachedGames !== null && cachedGames > 0 && !data && !loading) {
      loadStats();
    }
  }, [cachedGames]);

  const handleApplyFilters = (filters: OpeningDistributionFilters) => {
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
          {!cachedGames && (
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
