import { useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { useAnalysis } from "../context/AnalysisContext";
import StudyPicker from "../components/StudyPicker";
import GameFilters from "../components/GameFilters";
import ResultsTable from "../components/ResultsTable";
import Charts from "../components/Charts";

export default function AnalysisPage() {
  const { lichessToken, chessComUsername, cacheStatus } = useAuth();
  const {
    studies,
    selectedStudies,
    results,
    totalGames,
    matchedGames,
    loading,
    error,
    activeFilters,
    sidebarCollapsed,
    setSidebarCollapsed,
    fetchStudies,
    selectStudies,
    analyzeGames,
    debounceRef,
  } = useAnalysis();

  // Fetch studies when user logs in
  useEffect(() => {
    if (lichessToken) {
      fetchStudies();
    }
  }, [lichessToken, fetchStudies]);

  // Auto-analyze when studies are selected and cache is available
  useEffect(() => {
    // Clear any pending debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // If no studies selected, do nothing (results already cleared by selectStudies)
    if (selectedStudies.length === 0) {
      return;
    }

    // Only auto-analyze if cache has games
    if (cacheStatus?.cached_games > 0) {
      debounceRef.current = setTimeout(() => {
        analyzeGames();
      }, 300);
    }

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [selectedStudies, cacheStatus, analyzeGames, debounceRef]);

  const handleApplyFilters = async (filters) => {
    analyzeGames(filters);
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
              onSelectionChange={selectStudies}
              studies={studies}
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
