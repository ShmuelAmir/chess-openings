function ResultsTable({ results }) {
  if (!results || results.length === 0) {
    return (
      <div className="empty-state">
        <p>No deviations found! Either:</p>
        <ul style={{ textAlign: "left", marginTop: "1rem", color: "#888" }}>
          <li>You followed your repertoire perfectly 🎉</li>
          <li>No games matched your filters</li>
          <li>Your repertoire studies don't cover these openings</li>
        </ul>
      </div>
    );
  }

  const deviations = results.filter((r) => r.result_type === "deviation");
  const opponentLeft = results.filter(
    (r) => r.result_type === "opponent_left_book"
  );

  return (
    <div>
      <div className="stats">
        <div className="stat">
          <div className="stat-value">{results.length}</div>
          <div className="stat-label">Games Analyzed</div>
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

      <table className="results-table">
        <thead>
          <tr>
            <th>Game</th>
            <th>Opening</th>
            <th>Move #</th>
            <th>Result</th>
            <th>Your Move</th>
            <th>Correct Move</th>
            <th>Analyze</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, i) => (
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
                  <span style={{ color: "#888" }}>—</span>
                )}
              </td>
              <td>
                {result.result_type === "deviation" ? (
                  <span className="move-good">{result.correct_move}</span>
                ) : (
                  <span style={{ color: "#888" }}>
                    Opponent played: {result.opponent_move}
                  </span>
                )}
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
