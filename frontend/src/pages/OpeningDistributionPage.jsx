import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import GameFilters from "../components/GameFilters";
import OpeningCharts from "../components/OpeningCharts";

export default function OpeningDistributionPage() {
  const { chessComUsername } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async (filters) => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const params = new URLSearchParams({
        chess_com_username: chessComUsername,
        from_year: filters.fromYear,
        from_month: filters.fromMonth,
        to_year: filters.toYear,
        to_month: filters.toMonth,
      });

      // Add time classes
      if (filters.timeClasses && filters.timeClasses.length > 0) {
        filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
      }
      if (filters.ratedOnly) {
        params.append("rated", "true");
      }
      if (filters.colorFilter && filters.colorFilter !== "both") {
        params.append("color", filters.colorFilter);
      }

      const response = await fetch(`/api/opening-stats?${params}`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to fetch opening statistics");
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const hasResults = data !== null || loading;

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div
        className={`${hasResults ? "main-layout opening-layout" : "centered-layout"}`}
      >
        <div className="setup-panel opening-filters">
          <div className="section">
            <h2>Filters</h2>
            <p className="section-subtitle">
              Analyze your Chess.com games to see opening distribution
              statistics
            </p>
            <GameFilters
              onAnalyze={handleAnalyze}
              loading={loading}
              showUsernameField={false}
            />
          </div>
        </div>

        {hasResults && (
          <div className="results-panel opening-results">
            <div className="section">
              <h2>Opening Distribution</h2>
              {loading && (
                <div className="loading">Fetching opening statistics...</div>
              )}
              {!loading && data && <OpeningCharts data={data} />}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
