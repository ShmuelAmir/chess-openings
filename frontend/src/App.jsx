import { useState, useEffect } from "react";
import LichessAuth from "./components/LichessAuth";
import StudyPicker from "./components/StudyPicker";
import GameFilters from "./components/GameFilters";
import ResultsTable from "./components/ResultsTable";

function App() {
  const [lichessToken, setLichessToken] = useState(
    localStorage.getItem("lichess_token")
  );
  const [lichessUser, setLichessUser] = useState(null);
  const [selectedStudies, setSelectedStudies] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

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
        year: filters.year,
        month: filters.month,
        ...selectedStudies.map((id) => ["study_ids", id]),
      });

      // Add study_ids properly
      selectedStudies.forEach((id) => params.append("study_ids", id));

      if (filters.timeClass) {
        params.append("time_class", filters.timeClass);
      }
      if (filters.ratedOnly) {
        params.append("rated", "true");
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <h1>♟️ Chess Opening Analyzer</h1>
      <p style={{ textAlign: "center", marginBottom: "2rem", color: "#aaa" }}>
        Compare your Chess.com games against your Chessly repertoire (via
        Lichess Studies)
      </p>

      {error && <div className="error">{error}</div>}

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
            />
          </div>

          <div className="section">
            <h2>3. Fetch & Analyze Chess.com Games</h2>
            <GameFilters onAnalyze={handleAnalyze} loading={loading} />
          </div>

          {loading && <div className="loading">Analyzing games...</div>}

          {results && (
            <div className="section">
              <h2>4. Results</h2>
              <ResultsTable results={results} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default App;
