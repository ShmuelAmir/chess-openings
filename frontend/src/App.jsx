import { useState, useEffect } from "react";
import LichessAuth from "./components/LichessAuth";
import StudyPicker from "./components/StudyPicker";
import GameFilters from "./components/GameFilters";
import ResultsTable from "./components/ResultsTable";
import Charts from "./components/Charts";

function App() {
  const [lichessToken, setLichessToken] = useState(
    localStorage.getItem("lichess_token"),
  );
  const [lichessUser, setLichessUser] = useState(null);
  const [chessComUsername, setChessComUsername] = useState(
    localStorage.getItem("chess_com_username") || "",
  );
  const [studies, setStudies] = useState([]); // All user studies
  const [selectedStudies, setSelectedStudies] = useState([]);
  const [results, setResults] = useState(null);
  const [totalGames, setTotalGames] = useState(0);
  const [matchedGames, setMatchedGames] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  // Fetch Lichess user info when token is available
  useEffect(() => {
    if (lichessToken) {
      fetchLichessUser();
    }
  }, [lichessToken]);

  // Close profile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (showProfileMenu && !e.target.closest(".profile-menu-container")) {
        setShowProfileMenu(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, [showProfileMenu]);

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

  const handleChessComSave = (username) => {
    localStorage.setItem("chess_com_username", username);
    setChessComUsername(username);
  };

  const handleChessComClear = () => {
    localStorage.removeItem("chess_com_username");
    setChessComUsername("");
  };

  const isConnected = lichessToken && lichessUser && chessComUsername;

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

  // Welcome screen when not fully connected
  if (!isConnected) {
    return (
      <div className="app">
        <h1>♟️ Chess Opening Analyzer</h1>
        <p style={{ textAlign: "center", marginBottom: "2rem", color: "#aaa" }}>
          Compare your Chess.com games against your Chessly repertoire (via
          Lichess Studies)
        </p>

        <div className="welcome-screen">
          <div className="welcome-card">
            <h2>Connect Your Accounts</h2>
            <p className="welcome-subtitle">
              To get started, connect both your Lichess and Chess.com accounts
            </p>

            <div className="connection-cards">
              <div
                className={`connection-card ${lichessUser ? "connected" : ""}`}
              >
                <div className="connection-icon">
                  <img
                    src="https://lichess1.org/assets/logo/lichess-white.svg"
                    alt="Lichess"
                  />
                </div>
                <div className="connection-info">
                  <h3>Lichess</h3>
                  <p>For your opening repertoire studies</p>
                  {lichessUser ? (
                    <div className="connected-user">
                      <span className="checkmark">✓</span>
                      <span>
                        Connected as <strong>{lichessUser.username}</strong>
                      </span>
                      <button className="text-btn" onClick={handleLogout}>
                        Disconnect
                      </button>
                    </div>
                  ) : (
                    <LichessAuth
                      user={lichessUser}
                      onLogin={handleLogin}
                      onLogout={handleLogout}
                    />
                  )}
                </div>
              </div>

              <div
                className={`connection-card ${chessComUsername ? "connected" : ""}`}
              >
                <div className="connection-icon chess-com">
                  <span>♟</span>
                </div>
                <div className="connection-info">
                  <h3>Chess.com</h3>
                  <p>For your game history</p>
                  {chessComUsername ? (
                    <div className="connected-user">
                      <span className="checkmark">✓</span>
                      <span>
                        Username: <strong>{chessComUsername}</strong>
                      </span>
                      <button
                        className="text-btn"
                        onClick={handleChessComClear}
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const input = e.target.elements.username.value.trim();
                        if (input) handleChessComSave(input);
                      }}
                    >
                      <div className="chess-com-input">
                        <input
                          type="text"
                          name="username"
                          placeholder="Enter Chess.com username"
                        />
                        <button type="submit">Save</button>
                      </div>
                    </form>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`app ${hasResults ? "with-results" : ""}`}>
      <header className="app-header">
        <h1>♟️ Chess Opening Analyzer</h1>

        <div className="profile-menu-container">
          <button
            className="profile-btn"
            onClick={(e) => {
              e.stopPropagation();
              setShowProfileMenu(!showProfileMenu);
            }}
          >
            <span className="avatar">
              {lichessUser.username[0].toUpperCase()}
            </span>
          </button>

          {showProfileMenu && (
            <div className="profile-dropdown">
              <div className="profile-dropdown-header">Connected Accounts</div>

              <div className="profile-account">
                <img
                  src="https://lichess1.org/assets/logo/lichess-white.svg"
                  alt="Lichess"
                  className="account-icon"
                />
                <div className="account-details">
                  <span className="account-name">{lichessUser.username}</span>
                  <span className="account-type">Lichess</span>
                </div>
                <button className="text-btn small" onClick={handleLogout}>
                  Disconnect
                </button>
              </div>

              <div className="profile-account">
                <span className="account-icon chess-com-icon">♟</span>
                <div className="account-details">
                  <span className="account-name">{chessComUsername}</span>
                  <span className="account-type">Chess.com</span>
                </div>
                <button
                  className="text-btn small"
                  onClick={handleChessComClear}
                >
                  Change
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

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
    </div>
  );
}

export default App;
