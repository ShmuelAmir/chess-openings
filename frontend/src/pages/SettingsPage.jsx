import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import "../components/recall/recall.css";

async function readStudies(response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      response.status === 429
        ? "Lichess rate limit reached. Please wait a minute and try again."
        : data.detail || "Could not load your studies",
    );
  }
  return (await response.json()).studies;
}

/**
 * Settings: every owned study, with a switch to mark it "not repertoire".
 * Excluded studies leave the Repertoire, and so the Recall Gaps, the totals
 * and the Study filter.
 */
export default function SettingsPage() {
  const { lichessToken } = useAuth();

  const [studies, setStudies] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!lichessToken) return;
    fetch("/api/not-repertoire", {
      headers: { Authorization: `Bearer ${lichessToken}` },
    })
      .then(readStudies)
      .then(setStudies)
      .catch((err) => setError(err.message));
  }, [lichessToken]);

  const toggle = async (id) => {
    const excluded = studies
      .filter((study) => (study.id === id ? !study.excluded : study.excluded))
      .map((study) => study.id);

    setSaving(true);
    setError(null);
    try {
      const response = await fetch("/api/not-repertoire", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${lichessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ excluded }),
      });
      setStudies(await readStudies(response));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rv-settings">
      <h2>Settings</h2>
      <div className="rv-rail-title">Studies</div>
      <p className="rv-muted">
        Every study you own on Lichess is part of your Repertoire. Mark scratch
        or unrelated studies as "not repertoire" so they don't create Recall
        Gaps.
      </p>

      {error && <div className="error">{error}</div>}

      {!studies ? (
        !error && <div className="loading">Loading studies...</div>
      ) : studies.length === 0 ? (
        <p className="rv-muted">You don't own any Lichess studies yet.</p>
      ) : (
        <ul className="rv-settings-studies">
          {studies.map((study) => (
            <li key={study.id} className={study.excluded ? "excluded" : ""}>
              <span>
                <span className="rv-title">{study.opening_name}</span>
                {study.name !== study.opening_name && (
                  <span className="rv-muted"> · {study.name}</span>
                )}
              </span>
              <label className="rv-switch">
                <input
                  type="checkbox"
                  checked={study.excluded}
                  disabled={saving}
                  onChange={() => toggle(study.id)}
                />
                <span className="rv-switch-track" />
                Not repertoire
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
