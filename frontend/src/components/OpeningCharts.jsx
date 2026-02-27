import React, { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from "recharts";

const COLORS = [
  "#81b64c",
  "#f39c12",
  "#3498db",
  "#e74c3c",
  "#9b59b6",
  "#1abc9c",
  "#e67e22",
  "#95a5a6",
];

export default function OpeningCharts({ data }) {
  const [showAllOpenings, setShowAllOpenings] = useState(false);

  if (!data) return null;

  const {
    top_openings = [],
    categories = [],
    trends = [],
    top_opening_names = [],
  } = data;

  const displayedOpenings = showAllOpenings
    ? top_openings
    : top_openings.slice(0, 10);

  return (
    <div className="opening-charts">
      {/* 1. Most Played Openings Bar Chart */}
      <div className="chart-card">
        <h3>Most Played Openings</h3>
        <div className="chart-actions">
          <button
            className={`toggle-btn ${!showAllOpenings ? "active" : ""}`}
            onClick={() => setShowAllOpenings(false)}
          >
            Top 10
          </button>
          <button
            className={`toggle-btn ${showAllOpenings ? "active" : ""}`}
            onClick={() => setShowAllOpenings(true)}
          >
            All ({top_openings.length})
          </button>
        </div>
        <ResponsiveContainer
          width="100%"
          height={Math.max(300, displayedOpenings.length * 35)}
        >
          <BarChart
            data={displayedOpenings}
            layout="vertical"
            margin={{ top: 10, right: 30, left: 150, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis type="number" stroke="#888" />
            <YAxis
              dataKey="opening"
              type="category"
              stroke="#888"
              width={140}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#2a2a2a",
                border: "1px solid #444",
              }}
              formatter={(value, name) => [
                value,
                name === "games" ? "Games" : name,
              ]}
            />
            <Bar dataKey="games" fill="#81b64c" name="Games" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 2. Opening Categories Pie Chart */}
      <div className="chart-card">
        <h3>Opening Categories</h3>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={categories}
              dataKey="count"
              nameKey="category"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={({ category, percent }) =>
                `${category}: ${(percent * 100).toFixed(0)}%`
              }
              labelLine={{ stroke: "#666" }}
            >
              {categories.map((entry, index) => (
                <Cell
                  key={entry.category}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "#2a2a2a",
                border: "1px solid #444",
              }}
              formatter={(value, name) => [`${value} games`, name]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* 3. Win Rate by Opening */}
      <div className="chart-card">
        <h3>Performance by Opening</h3>
        <ResponsiveContainer
          width="100%"
          height={Math.max(300, displayedOpenings.length * 35)}
        >
          <BarChart
            data={displayedOpenings}
            layout="vertical"
            margin={{ top: 10, right: 30, left: 150, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis type="number" stroke="#888" />
            <YAxis
              dataKey="opening"
              type="category"
              stroke="#888"
              width={140}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#2a2a2a",
                border: "1px solid #444",
              }}
              formatter={(value, name) => {
                if (name === "win_rate") return [`${value}%`, "Win Rate"];
                return [value, name.charAt(0).toUpperCase() + name.slice(1)];
              }}
            />
            <Legend />
            <Bar dataKey="wins" stackId="result" fill="#81b64c" name="Wins" />
            <Bar dataKey="draws" stackId="result" fill="#f39c12" name="Draws" />
            <Bar
              dataKey="losses"
              stackId="result"
              fill="#e74c3c"
              name="Losses"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 4. Opening Trends Over Time */}
      {trends.length > 0 && (
        <div className="chart-card">
          <h3>Opening Trends (Top 5)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart
              data={trends}
              margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="month" stroke="#888" />
              <YAxis stroke="#888" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#2a2a2a",
                  border: "1px solid #444",
                }}
              />
              <Legend />
              {top_opening_names.map((name, index) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={COLORS[index % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 5. Win Rate Summary Table */}
      <div className="chart-card">
        <h3>Opening Statistics</h3>
        <div className="stats-table-wrapper">
          <table className="stats-table">
            <thead>
              <tr>
                <th>Opening</th>
                <th>Games</th>
                <th>Wins</th>
                <th>Draws</th>
                <th>Losses</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {displayedOpenings.map((row) => (
                <tr key={row.opening}>
                  <td className="opening-name">{row.opening}</td>
                  <td>{row.games}</td>
                  <td className="win">{row.wins}</td>
                  <td className="draw">{row.draws}</td>
                  <td className="loss">{row.losses}</td>
                  <td>
                    <span
                      className={`win-rate ${
                        row.win_rate >= 50 ? "positive" : "negative"
                      }`}
                    >
                      {row.win_rate}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. Diversity Index */}
      <div className="chart-card stats-summary">
        <h3>Summary Statistics</h3>
        <div className="summary-grid">
          <div className="summary-item">
            <span className="summary-value">{data.total_games}</span>
            <span className="summary-label">Total Games</span>
          </div>
          <div className="summary-item">
            <span className="summary-value">{data.unique_openings}</span>
            <span className="summary-label">Unique Openings</span>
          </div>
          <div className="summary-item">
            <span className="summary-value">
              {top_openings[0]?.opening || "N/A"}
            </span>
            <span className="summary-label">Most Played</span>
          </div>
          <div className="summary-item">
            <span className="summary-value">
              {(() => {
                const best = [...top_openings]
                  .filter((o) => o.games >= 5)
                  .sort((a, b) => b.win_rate - a.win_rate)[0];
                return best ? `${best.opening} (${best.win_rate}%)` : "N/A";
              })()}
            </span>
            <span className="summary-label">Best Win Rate (5+ games)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
