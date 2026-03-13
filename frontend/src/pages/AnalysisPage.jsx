import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import StudyPicker from "../components/StudyPicker";
import GameFilters from "../components/GameFilters";
import ResultsTable from "../components/ResultsTable";
import Charts from "../components/Charts";

export default function AnalysisPage() {
  const { lichessToken, chessComUsername, cacheStatus } = useAuth();

  const [studies, setStudies] = useState([]);
  const [selectedStudies, setSelectedStudies] = useState([]);
  const [results, setResults] = useState(null);
  const [totalGames, setTotalGames] = useState(0);
  const [matchedGames, setMatchedGames] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Current filters state
  const [activeFilters, setActiveFilters] = useState(null);

  // Load games and analyze
  const loadGames = useCallback(
    async (filters = null) => {
      if (!chessComUsername || !lichessToken) return;
      if (selectedStudies.length === 0) return;

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

        selectedStudies.forEach((id) => params.append("study_ids", id));

        const selectedStudyNames = studies
          .filter((s) => selectedStudies.includes(s.id))
          .map((s) => s.name);
        selectedStudyNames.forEach((name) =>
          params.append("study_names", name),
        );

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

        const response = await fetch(`/api/analyze?${params}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${lichessToken}` },
        });

        if (!response.ok) {
          throw new Error("Analysis failed");
        }

        const data = await response.json();
        setResults(data.results);
        setTotalGames(data.total_games || 0);
        setMatchedGames(data.filtered_by_opening || 0);
        setActiveFilters(defaultFilters);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [chessComUsername, lichessToken, selectedStudies, studies, activeFilters],
  );

  // Debounce timer ref
  const debounceRef = useRef(null);

  // Auto-load when studies are selected (with debounce)
  useEffect(() => {
    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // If no studies selected, clear results immediately
    if (selectedStudies.length === 0) {
      setResults(null);
      setTotalGames(0);
      setMatchedGames(0);
      return;
    }

    // Debounce the API call
    if (cacheStatus?.cached_games > 0) {
      debounceRef.current = setTimeout(() => {
        loadGames();
      }, 300);
    }

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [selectedStudies, cacheStatus]);

  const handleApplyFilters = async (filters) => {
    if (selectedStudies.length === 0) {
      setError("Select a repertoire study first");
      return;
    }
    loadGames(filters);
  };

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div className={`main-layout ${sidebarCollapsed ? "collapsed" : ""}`}>
        <div className={`setup-panel ${sidebarCollapsed ? "collapsed" : ""}`}>
          <button
            className="collapse-btn"
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? "Expand" : "Collapse"}
          >
            {sidebarCollapsed ? "→" : "←"}
          </button>

          {/* Study Picker */}
          <div className="section">
            <h2>Repertoire Studies</h2>
            <StudyPicker
              token={lichessToken}
              selectedStudies={selectedStudies}
              onSelectionChange={setSelectedStudies}
              onStudiesLoaded={setStudies}
            />
          </div>

          {/* Filters */}
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

        <div className="results-panel">
          {!chessComUsername && (
            <div className="empty-state">
              <p>Set your Chess.com username on the home page to get started</p>
            </div>
          )}

          {chessComUsername && !cacheStatus?.cached_games && (
            <div className="empty-state">
              <p>Click "Sync" to fetch your Chess.com games</p>
            </div>
          )}

          {chessComUsername &&
            cacheStatus?.cached_games > 0 &&
            selectedStudies.length === 0 &&
            !loading &&
            !results && (
              <div className="empty-state">
                <p>Select a repertoire study to analyze your games</p>
              </div>
            )}

          {loading && (
            <div className="section">
              <div className="loading">Analyzing games...</div>
            </div>
          )}

          {!loading && results && (
            <>
              <div className="section results-section">
                <ResultsTable
                  results={results}
                  totalGames={totalGames}
                  filteredByOpening={matchedGames}
                />
              </div>

              <div className="section charts-section">
                <Charts
                  results={results}
                  totalGames={totalGames}
                  filteredByOpening={matchedGames}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
