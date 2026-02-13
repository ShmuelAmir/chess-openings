import { useState } from "react";

function ResultsTable({ results, totalGames, filteredByOpening }) {
  const [sortConfig, setSortConfig] = useState({
    key: "game_date",
    direction: "desc",
  });

  if (!results || results.length === 0) {
    return (
      <div className="empty-state">
        <p>No deviations found! Either:</p>
        <ul style={{ textAlign: "left", marginTop: "1rem", color: "#888" }}>
          <li>You followed your repertoire perfectly 🎉</li>
          <li>No games matched your filters</li>
          <li>Your repertoire studies don't cover these openings</li>
        </ul>
        {totalGames > 0 && (
          <p style={{ marginTop: "1rem", color: "#666" }}>
            ({totalGames} games fetched, {filteredByOpening || 0} matched your
            opening names)
          </p>
        )}
      </div>
    );
  }

  const deviations = results.filter((r) => r.result_type === "deviation");
  const opponentLeft = results.filter(
    (r) => r.result_type === "opponent_left_book",
  );

  // Sort results
  const sortedResults = [...results].sort((a, b) => {
    const aVal = a[sortConfig.key];
    const bVal = b[sortConfig.key];

    if (aVal === null || aVal === undefined) return 1;
    if (bVal === null || bVal === undefined) return -1;

    const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortConfig.direction === "asc" ? comparison : -comparison;
  });

  const handleSort = (key) => {
    setSortConfig({
      key,
      direction:
        sortConfig.key === key && sortConfig.direction === "asc"
          ? "desc"
          : "asc",
    });
  };

  const SortHeader = ({ label, sortKey }) => (
    <th
      onClick={() => handleSort(sortKey)}
      style={{ cursor: "pointer", userSelect: "none" }}
    >
      {label}
      {sortConfig.key === sortKey && (
        <span style={{ marginLeft: "0.5rem", color: "#81b64c" }}>
          {sortConfig.direction === "asc" ? "↑" : "↓"}
        </span>
      )}
    </th>
  );

  return (
    <div>
      <div className="stats">
        <div className="stat">
          <div className="stat-value">{results.length}</div>
          <div className="stat-label">Total Results</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: "#e74c3c" }}>
            {deviations.length}
          </div>
          <div className="stat-label">Your Deviations</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: "#f39c12" }}>
            {opponentLeft.length}
          </div>
          <div className="stat-label">Opponent Left Book</div>
        </div>
      </div>

      <p className="filter-info">
        Analyzed {filteredByOpening || 0} games matching your openings (from{" "}
        {totalGames || 0} total)
      </p>

      <table className="results-table">
        <thead>
          <tr>
            <th>Game</th>
            <SortHeader label="Date" sortKey="game_date" />
            <th>Color</th>
            <th>Study</th>
            <SortHeader label="Opening" sortKey="opening_name" />
            <SortHeader label="Move #" sortKey="move_number" />
            <th>Result</th>
            <th>Move Played</th>
            <th>Correct Move</th>
            <th>Analyze</th>
          </tr>
        </thead>
        <tbody>
          {sortedResults.map((result, i) => (
            <tr key={i}>
              <td>
                <a
                  href={result.game_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="link"
                >
                  View
                </a>
              </td>
              <td className="date-cell">{result.game_date || "—"}</td>
              <td>
                <span
                  className={`color-dot ${result.user_color}`}
                  title={result.user_color}
                ></span>
              </td>
              <td>
                <span className="study-name">{result.study_name || "—"}</span>
              </td>
              <td>{result.opening_name}</td>
              <td>{result.move_number}</td>
              <td>
                {result.result_type === "deviation" ? (
                  <span className="result-deviation">You deviated</span>
                ) : (
                  <span className="result-opponent">Opponent left book</span>
                )}
              </td>
              <td>
                {result.result_type === "deviation" ? (
                  <span className="move-bad">{result.your_move}</span>
                ) : (
                  <span className="move-opponent">{result.opponent_move}</span>
                )}
              </td>
              <td>
                <span
                  className={
                    result.variation_count > 1
                      ? "move-good multiple-variations"
                      : "move-good"
                  }
                  title={
                    result.variation_count > 1
                      ? `${result.variation_count} variations available in your repertoire`
                      : ""
                  }
                >
                  {result.correct_move}
                </span>
              </td>
              <td>
                {result.analysis_url && (
                  <a
                    href={result.analysis_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="link"
                  >
                    🔗 Lichess
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ResultsTable;
