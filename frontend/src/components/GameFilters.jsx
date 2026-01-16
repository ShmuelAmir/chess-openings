import { useState } from "react";

function GameFilters({ onAnalyze, loading }) {
  const currentDate = new Date();
  const [username, setUsername] = useState("");
  const [year, setYear] = useState(currentDate.getFullYear());
  const [month, setMonth] = useState(currentDate.getMonth() + 1);
  const [timeClass, setTimeClass] = useState("");
  const [ratedOnly, setRatedOnly] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!username.trim()) return;

    onAnalyze({
      username: username.trim(),
      year,
      month,
      timeClass: timeClass || null,
      ratedOnly,
    });
  };

  const months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];

  const years = [];
  for (let y = currentDate.getFullYear(); y >= 2010; y--) {
    years.push(y);
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-group" style={{ flex: 2 }}>
          <label>Chess.com Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter your Chess.com username"
            required
          />
        </div>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Month</label>
          <select
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {months.map((name, i) => (
              <option key={i} value={i + 1}>
                {name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Year</label>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Time Control</label>
          <select
            value={timeClass}
            onChange={(e) => setTimeClass(e.target.value)}
          >
            <option value="">All</option>
            <option value="bullet">Bullet</option>
            <option value="blitz">Blitz</option>
            <option value="rapid">Rapid</option>
            <option value="daily">Daily</option>
          </select>
        </div>
      </div>

      <div className="form-row">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={ratedOnly}
            onChange={(e) => setRatedOnly(e.target.checked)}
          />
          Rated games only
        </label>
      </div>

      <button type="submit" disabled={loading || !username.trim()}>
        {loading ? "Analyzing..." : "Analyze Games"}
      </button>
    </form>
  );
}

export default GameFilters;
