import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import StudyPicker from "../components/StudyPicker";
import GameFilters from "../components/GameFilters";
import ResultsTable from "../components/ResultsTable";
import Charts from "../components/Charts";

export default function AnalysisPage() {
  const { lichessToken, chessComUsername } = useAuth();

  const [studies, setStudies] = useState([]);
  const [selectedStudies, setSelectedStudies] = useState([]);
  const [results, setResults] = useState(null);
  const [totalGames, setTotalGames] = useState(0);
  const [matchedGames, setMatchedGames] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const handleAnalyze = async (filters) => {
    if (selectedStudies.length === 0) {
      setError("Please select at least one study");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const params = new URLSearchParams({
        chess_com_username: chessComUsername,
        from_year: filters.fromYear,
        from_month: filters.fromMonth,
        to_year: filters.toYear,
        to_month: filters.toMonth,
      });

      // Add study_ids properly
      selectedStudies.forEach((id) => params.append("study_ids", id));

      // Add study names for filtering games by opening
      const selectedStudyNames = studies
        .filter((s) => selectedStudies.includes(s.id))
        .map((s) => s.name);
      selectedStudyNames.forEach((name) => params.append("study_names", name));

      // Add time classes (multiple selection)
      if (filters.timeClasses && filters.timeClasses.length > 0) {
        filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
      }
      if (filters.ratedOnly) {
        params.append("rated", "true");
      }
      if (filters.colorFilter && filters.colorFilter !== "both") {
        params.append("color", filters.colorFilter);
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const hasResults = results !== null || loading;

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div
        className={`${hasResults ? "main-layout" : "centered-layout"} ${
          hasResults && sidebarCollapsed ? "collapsed" : ""
        }`}
      >
        <div className={`setup-panel ${sidebarCollapsed ? "collapsed" : ""}`}>
          {hasResults && (
            <button
              className="collapse-btn"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title={sidebarCollapsed ? "Expand" : "Collapse"}
            >
              {sidebarCollapsed ? "→" : "←"}
            </button>
          )}

          <div className="section">
            <h2>1. Select Your Repertoire Studies</h2>
            <StudyPicker
              token={lichessToken}
              selectedStudies={selectedStudies}
              onSelectionChange={setSelectedStudies}
              onStudiesLoaded={setStudies}
            />
          </div>

          <div className="section">
            <h2>2. Fetch & Analyze Games</h2>
            <GameFilters
              onAnalyze={handleAnalyze}
              loading={loading}
              showUsernameField={false}
            />
          </div>
        </div>

        {hasResults && (
          <div className="results-panel">
            <div className="section results-section">
              <h2>3. Results</h2>
              {loading && <div className="loading">Analyzing games...</div>}
              {!loading && results && (
                <ResultsTable
                  results={results}
                  totalGames={totalGames}
                  filteredByOpening={matchedGames}
                />
              )}
            </div>

            {!loading && results && (
              <div className="section charts-section">
                <Charts
                  results={results}
                  totalGames={totalGames}
                  filteredByOpening={matchedGames}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
