import { useState } from "react";

function GameFilters({ onAnalyze, loading, showUsernameField = true }) {
  const currentDate = new Date();
  const [username, setUsername] = useState("");
  const [fromYear, setFromYear] = useState(currentDate.getFullYear());
  const [fromMonth, setFromMonth] = useState(1);
  const [toYear, setToYear] = useState(currentDate.getFullYear());
  const [toMonth, setToMonth] = useState(currentDate.getMonth() + 1);
  const [timeClasses, setTimeClasses] = useState({
    bullet: true,
    blitz: true,
    rapid: true,
    daily: false,
  });
  const [colorFilter, setColorFilter] = useState("both"); // "white", "black", or "both"
  const [ratedOnly, setRatedOnly] = useState(false);

  const handleTimeClassToggle = (tc) => {
    setTimeClasses((prev) => ({ ...prev, [tc]: !prev[tc] }));
  };

  const selectAllTimeClasses = () => {
    setTimeClasses({ bullet: true, blitz: true, rapid: true, daily: true });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (showUsernameField && !username.trim()) return;

    // Get selected time classes as array
    const selectedTimeClasses = Object.entries(timeClasses)
      .filter(([_, selected]) => selected)
      .map(([tc, _]) => tc);

    onAnalyze({
      username: username.trim(),
      fromYear,
      fromMonth,
      toYear,
      toMonth,
      timeClasses: selectedTimeClasses.length > 0 ? selectedTimeClasses : null,
      colorFilter,
      ratedOnly,
    });
  };

  const allSelected = Object.values(timeClasses).every((v) => v);
  const noneSelected = Object.values(timeClasses).every((v) => !v);

  // Validate date range
  const fromDate = new Date(fromYear, fromMonth - 1);
  const toDate = new Date(toYear, toMonth - 1);
  const isValidRange = fromDate <= toDate;

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

  // Quick select helpers
  const selectFullYear = (year) => {
    setFromYear(year);
    setFromMonth(1);
    setToYear(year);
    setToMonth(12);
  };

  const selectLastNMonths = (n) => {
    const end = new Date();
    const start = new Date();
    start.setMonth(start.getMonth() - n + 1);

    setFromYear(start.getFullYear());
    setFromMonth(start.getMonth() + 1);
    setToYear(end.getFullYear());
    setToMonth(end.getMonth() + 1);
  };

  return (
    <form onSubmit={handleSubmit}>
      {showUsernameField && (
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
      )}

      <div className="date-range-section">
        <label className="section-label">Date Range</label>

        <div className="quick-select">
          <button
            type="button"
            className="secondary small"
            onClick={() => selectLastNMonths(0.25)}
          >
            Last week
          </button>
          <button
            type="button"
            className="secondary small"
            onClick={() => selectLastNMonths(1)}
          >
            Last month
          </button>
          <button
            type="button"
            className="secondary small"
            onClick={() => selectLastNMonths(3)}
          >
            Last 3 months
          </button>
          <button
            type="button"
            className="secondary small"
            onClick={() => selectLastNMonths(6)}
          >
            Last 6 months
          </button>
          <button
            type="button"
            className="secondary small"
            onClick={() => selectLastNMonths(12)}
          >
            Last year
          </button>
        </div>

        <div className="date-range-row">
          <div className="date-picker">
            <span className="date-label">From</span>
            <select
              value={fromMonth}
              onChange={(e) => setFromMonth(Number(e.target.value))}
            >
              {months.map((name, i) => (
                <option key={i} value={i + 1}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={fromYear}
              onChange={(e) => setFromYear(Number(e.target.value))}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>

          <span className="date-separator">→</span>

          <div className="date-picker">
            <span className="date-label">To</span>
            <select
              value={toMonth}
              onChange={(e) => setToMonth(Number(e.target.value))}
            >
              {months.map((name, i) => (
                <option key={i} value={i + 1}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={toYear}
              onChange={(e) => setToYear(Number(e.target.value))}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
        </div>

        {!isValidRange && (
          <p className="error-text">End date must be after start date</p>
        )}
      </div>

      <div className="form-row">
        <div className="form-group" style={{ flex: 1 }}>
          <label>Time Controls</label>
          <div className="time-controls-row">
            {[
              { id: "bullet", icon: "⚡", label: "Bullet" },
              { id: "blitz", icon: "🔥", label: "Blitz" },
              { id: "rapid", icon: "⏱️", label: "Rapid" },
              { id: "daily", icon: "📅", label: "Daily" },
            ].map((tc) => (
              <button
                key={tc.id}
                type="button"
                className={`time-control-pill ${
                  timeClasses[tc.id] ? "active" : ""
                }`}
                onClick={() => handleTimeClassToggle(tc.id)}
              >
                <span className="tc-icon">{tc.icon}</span>
                <span className="tc-label">{tc.label}</span>
              </button>
            ))}
          </div>
          {!allSelected && (
            <button
              type="button"
              className="secondary small"
              onClick={selectAllTimeClasses}
              style={{ marginTop: "0.5rem" }}
            >
              Select All
            </button>
          )}
        </div>
      </div>

      <div className="form-row">
        <div className="form-group" style={{ flex: 1 }}>
          <label>Play As</label>
          <div className="color-filter-row">
            {[
              { id: "both", label: "Both" },
              { id: "white", label: "White", dot: true },
              { id: "black", label: "Black", dot: true },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`color-filter-pill ${
                  colorFilter === opt.id ? "active" : ""
                }`}
                onClick={() => setColorFilter(opt.id)}
              >
                {opt.dot && (
                  <span className={`color-dot small ${opt.id}`}></span>
                )}
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
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

      <button
        type="submit"
        disabled={
          loading ||
          (showUsernameField && !username.trim()) ||
          noneSelected ||
          !isValidRange
        }
      >
        {loading ? "Analyzing..." : "Analyze Games"}
      </button>
      {noneSelected && (
        <p className="error-text">Please select at least one time control</p>
      )}
    </form>
  );
}

export default GameFilters;
