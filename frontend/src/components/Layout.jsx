import { useState, useEffect } from "react";
import { Outlet, Link, useLocation } from "@tanstack/react-router";
import { AuthProvider, useAuth } from "../context/AuthContext";
import LichessAuth from "./LichessAuth";

function LayoutContent() {
  const location = useLocation();
  const {
    lichessToken,
    lichessUser,
    chessComUsername,
    isConnected,
    handleLogin,
    handleLogout,
    handleChessComSave,
    handleChessComClear,
  } = useAuth();

  const [showProfileMenu, setShowProfileMenu] = useState(false);

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
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>♟️ Chess Opening Analyzer</h1>
          <nav className="header-nav">
            <Link
              to="/"
              className={`nav-link ${location.pathname === "/" ? "active" : ""}`}
            >
              Repertoire Analysis
            </Link>
            <Link
              to="/openings"
              className={`nav-link ${location.pathname === "/openings" ? "active" : ""}`}
            >
              Opening Distribution
            </Link>
          </nav>
        </div>

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

      <Outlet />
    </div>
  );
}

export default function Layout() {
  return (
    <AuthProvider>
      <LayoutContent />
    </AuthProvider>
  );
}
