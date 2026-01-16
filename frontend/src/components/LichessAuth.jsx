import { useState, useEffect } from "react";

function LichessAuth({ user, onLogin, onLogout }) {
  const [loading, setLoading] = useState(false);

  // Handle OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (code && state) {
      exchangeToken(code, state);
    }
  }, []);

  const startAuth = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/auth/lichess");
      const data = await response.json();

      // Store state for verification
      sessionStorage.setItem("lichess_oauth_state", data.state);

      // Redirect to Lichess
      window.location.href = data.auth_url;
    } catch (err) {
      console.error("Failed to start auth:", err);
      setLoading(false);
    }
  };

  const exchangeToken = async (code, state) => {
    const storedState = sessionStorage.getItem("lichess_oauth_state");

    if (state !== storedState) {
      console.error("State mismatch");
      return;
    }

    sessionStorage.removeItem("lichess_oauth_state");

    try {
      const response = await fetch(
        `/api/auth/callback?code=${code}&state=${state}`,
        { method: "POST" }
      );

      if (response.ok) {
        const data = await response.json();
        onLogin(data.access_token);

        // Clean URL
        window.history.replaceState({}, "", "/");
      }
    } catch (err) {
      console.error("Token exchange failed:", err);
    }
  };

  if (user) {
    return (
      <div className="user-info">
        <span>
          ✓ Connected as <strong>{user.username}</strong>
        </span>
        <button className="secondary" onClick={onLogout}>
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <button onClick={startAuth} disabled={loading}>
      {loading ? "Connecting..." : "Connect with Lichess"}
    </button>
  );
}

export default LichessAuth;
