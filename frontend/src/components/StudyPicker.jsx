import { useState, useEffect } from "react";

function StudyPicker({
  token,
  selectedStudies,
  onSelectionChange,
  onStudiesLoaded,
}) {
  const [studies, setStudies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStudies();
  }, [token]);

  const fetchStudies = async () => {
    try {
      const response = await fetch("/api/lichess/studies", {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch studies");
      }

      const data = await response.json();
      const loadedStudies = data.studies || [];
      setStudies(loadedStudies);
      // Pass studies to parent for filtering
      if (onStudiesLoaded) {
        onStudiesLoaded(loadedStudies);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleStudy = (studyId) => {
    if (selectedStudies.includes(studyId)) {
      onSelectionChange(selectedStudies.filter((id) => id !== studyId));
    } else {
      onSelectionChange([...selectedStudies, studyId]);
    }
  };

  if (loading) {
    return <div className="loading">Loading studies...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (studies.length === 0) {
    return (
      <div className="empty-state">
        <p>No studies found.</p>
        <p>
          Create studies on{" "}
          <a
            href="https://lichess.org/study"
            target="_blank"
            rel="noopener noreferrer"
            className="link"
          >
            lichess.org/study
          </a>{" "}
          with your Chessly repertoire.
        </p>
      </div>
    );
  }

  return (
    <div>
      <p style={{ marginBottom: "1rem", color: "#aaa" }}>
        Select the studies containing your opening repertoire (one study per
        opening):
      </p>
      <div className="studies-list">
        {studies.map((study) => (
          <div
            key={study.id}
            className={`study-item ${
              selectedStudies.includes(study.id) ? "selected" : ""
            }`}
            onClick={() => toggleStudy(study.id)}
          >
            <input
              type="checkbox"
              checked={selectedStudies.includes(study.id)}
              onChange={() => toggleStudy(study.id)}
            />
            <span>{study.name}</span>
            <span style={{ color: "#666", fontSize: "0.85rem" }}>
              ({study.chapters?.length || 0} chapters)
            </span>
          </div>
        ))}
      </div>
      {selectedStudies.length > 0 && (
        <p style={{ marginTop: "1rem", color: "#81b64c" }}>
          ✓ {selectedStudies.length} study(ies) selected
        </p>
      )}
    </div>
  );
}

export default StudyPicker;
