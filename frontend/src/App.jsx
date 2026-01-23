import { useState, useEffect } from "react";
import LichessAuth from "./components/LichessAuth";
import StudyPicker from "./components/StudyPicker";
import GameFilters from "./components/GameFilters";
import ResultsTable from "./components/ResultsTable";
import Charts from "./components/Charts";

function App() {
  const [lichessToken, setLichessToken] = useState(
    localStorage.getItem("lichess_token")
  );
  const [lichessUser, setLichessUser] = useState(null);
  const [studies, setStudies] = useState([]); // All user studies
  const [selectedStudies, setSelectedStudies] = useState([]);
  const [results, setResults] = useState(null);
  const [totalGames, setTotalGames] = useState(0);
  const [matchedGames, setMatchedGames] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  // Fetch Lichess user info when token is available
  useEffect(() => {
    if (lichessToken) {
      fetchLichessUser();
    }
  }, [lichessToken]);

  const fetchLichessUser = async () => {
    try {
      const response = await fetch("/api/lichess/me", {
        headers: { Authorization: `Bearer ${lichessToken}` },
      });
      if (response.ok) {
        const user = await response.json();
        setLichessUser(user);
      } else {
        // Token invalid, clear it
        handleLogout();
      }
    } catch (err) {
      console.error("Failed to fetch Lichess user:", err);
    }
  };

  const handleLogin = (token) => {
    localStorage.setItem("lichess_token", token);
    setLichessToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem("lichess_token");
    setLichessToken(null);
    setLichessUser(null);
    setSelectedStudies([]);
    setResults(null);
  };

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
        chess_com_username: filters.username,
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
    <div className={`app ${hasResults ? "with-results" : ""}`}>
      <h1>♟️ Chess Opening Analyzer</h1>
      <p style={{ textAlign: "center", marginBottom: "2rem", color: "#aaa" }}>
        Compare your Chess.com games against your Chessly repertoire (via
        Lichess Studies)
      </p>

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
            <h2>1. Connect Lichess Account</h2>
            <LichessAuth
              user={lichessUser}
              onLogin={handleLogin}
              onLogout={handleLogout}
            />
          </div>

          {lichessToken && lichessUser && (
            <>
              <div className="section">
                <h2>2. Select Your Repertoire Studies</h2>
                <StudyPicker
                  token={lichessToken}
                  selectedStudies={selectedStudies}
                  onSelectionChange={setSelectedStudies}
                  onStudiesLoaded={setStudies}
                />
              </div>

              <div className="section">
                <h2>3. Fetch & Analyze Chess.com Games</h2>
                <GameFilters onAnalyze={handleAnalyze} loading={loading} />
              </div>
            </>
          )}
        </div>

        {hasResults && (
          <div className="results-panel">
            <div className="section results-section">
              <h2>4. Results</h2>
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
    </div>
  );
}

export default App;
