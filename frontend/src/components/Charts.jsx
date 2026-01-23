import React, { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

function groupBy(arr, keyFn) {
  return arr.reduce((acc, item) => {
    const key = keyFn(item);
    acc[key] = acc[key] || [];
    acc[key].push(item);
    return acc;
  }, {});
}

function formatDateLabel(dateStr, granularity) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (granularity === "month") {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }
  // weekly: year-week
  const firstJan = new Date(d.getFullYear(), 0, 1);
  const week = Math.ceil(
    ((d - firstJan) / 86400000 + firstJan.getDay() + 1) / 7
  );
  return `${d.getFullYear()}-W${String(week).padStart(2, "0")}`;
}

export default function Charts({
  results = [],
  totalGames = 0,
  filteredByOpening = 0,
}) {
  const [granularity, setGranularity] = useState("month"); // "week" | "month"
  const [selectedOpening, setSelectedOpening] = useState("");

  const deviations = useMemo(
    () => results.filter((r) => r.result_type === "deviation"),
    [results]
  );
  const opponentLeft = useMemo(
    () => results.filter((r) => r.result_type === "opponent_left_book"),
    [results]
  );

  // 1) Deviation Rate Over Time
  const timeSeries = useMemo(() => {
    const byPeriod = groupBy(
      results.filter((r) => r.game_date),
      (r) => formatDateLabel(r.game_date, granularity)
    );
    const data = Object.entries(byPeriod)
      .map(([period, items]) => {
        const total = items.length;
        const yourDev = items.filter(
          (i) => i.result_type === "deviation"
        ).length;
        const oppLeft = items.filter(
          (i) => i.result_type === "opponent_left_book"
        ).length;
        return {
          period,
          yourDeviationRate: Math.round((yourDev / total) * 100),
          opponentLeftRate: Math.round((oppLeft / total) * 100),
          total,
        };
      })
      .sort((a, b) => a.period.localeCompare(b.period));
    return data;
  }, [results, granularity]);

  // 2) Opening Breakdown (stacked bar)
  const openingBreakdown = useMemo(() => {
    const byOpening = groupBy(results, (r) => r.opening_name || "Unknown");
    const rows = Object.entries(byOpening).map(([opening, items]) => {
      const yourDev = items.filter((i) => i.result_type === "deviation").length;
      const oppLeft = items.filter(
        (i) => i.result_type === "opponent_left_book"
      ).length;
      return { opening, yourDev, oppLeft, total: items.length };
    });
    return rows.sort((a, b) => b.total - a.total).slice(0, 15); // top 15 openings
  }, [results]);

  // 3) Move Number Distribution (histogram buckets)
  const moveBuckets = useMemo(() => {
    const buckets = {
      "1-5": 0,
      "6-10": 0,
      "11-15": 0,
      "16-20": 0,
      "21+": 0,
    };
    deviations.forEach((d) => {
      const m = d.move_number || 0;
      if (m <= 5) buckets["1-5"]++;
      else if (m <= 10) buckets["6-10"]++;
      else if (m <= 15) buckets["11-15"]++;
      else if (m <= 20) buckets["16-20"]++;
      else buckets["21+"]++;
    });
    return Object.entries(buckets).map(([range, count]) => ({ range, count }));
  }, [deviations]);

  // 4) Color Analysis (pie)
  const colorPie = useMemo(() => {
    const white = deviations.filter((d) => d.user_color === "white").length;
    const black = deviations.filter((d) => d.user_color === "black").length;
    return [
      { name: "White", value: white },
      { name: "Black", value: black },
    ];
  }, [deviations]);

  // 5) Variation Distribution per Opening (stacked bar)
  const variationByOpening = useMemo(() => {
    const byOpening = groupBy(deviations, (r) => r.opening_name || "Unknown");
    const rows = Object.entries(byOpening).map(([opening, items]) => {
      const v1 = items.filter((i) => (i.variation_count || 0) === 1).length;
      const v2 = items.filter((i) => (i.variation_count || 0) === 2).length;
      const v3 = items.filter((i) => (i.variation_count || 0) === 3).length;
      const v4plus = items.filter((i) => (i.variation_count || 0) >= 4).length;
      return { opening, v1, v2, v3, v4plus, total: items.length };
    });
    return rows.sort((a, b) => b.total - a.total).slice(0, 12); // top 12 openings
  }, [deviations]);

  // Opening options for Chapter Distribution selector
  const openingOptions = useMemo(() => {
    const set = new Set(
      (results || []).map((r) => r.opening_name || "Unknown")
    );
    return Array.from(set).sort();
  }, [results]);

  // Initialize default selected opening when results change
  React.useEffect(() => {
    if (!selectedOpening) {
      if (openingOptions.includes("Vienna")) {
        setSelectedOpening("Vienna");
      } else if (openingOptions.length > 0) {
        setSelectedOpening(openingOptions[0]);
      }
    } else if (
      !openingOptions.includes(selectedOpening) &&
      openingOptions.length > 0
    ) {
      setSelectedOpening(openingOptions[0]);
    }
  }, [openingOptions, selectedOpening]);

  function extractChapterName(studyName = "") {
    if (!studyName) return "Unknown";
    // Prefer pattern: "Study - Chapter"
    if (studyName.includes(" - ")) {
      const parts = studyName.split(" - ");
      return parts[1] ? parts[1].trim() : parts[0].trim();
    }
    // Fallback: after colon
    if (studyName.includes(":")) {
      const idx = studyName.indexOf(":");
      return studyName.slice(idx + 1).trim() || studyName.trim();
    }
    return studyName.trim();
  }

  // 6) Chapter Distribution for selected opening
  const chapterDistribution = useMemo(() => {
    if (!selectedOpening) return [];
    const filtered = (results || []).filter(
      (r) => (r.opening_name || "Unknown") === selectedOpening
    );
    const byChapter = groupBy(filtered, (r) =>
      extractChapterName(r.study_name)
    );
    const rows = Object.entries(byChapter).map(([chapter, items]) => ({
      chapter,
      count: items.length,
    }));
    return rows.sort((a, b) => b.count - a.count).slice(0, 20); // top 20 chapters
  }, [results, selectedOpening]);

  const COLORS = ["#81b64c", "#f39c12", "#3498db", "#e74c3c", "#9b59b6"]; // general palette

  return (
    <div className="charts">
      <div className="charts-header">
        <h2>Insights</h2>
        <div className="granularity">
          <label>Time group:</label>
          <button
            className={granularity === "week" ? "pill active" : "pill"}
            onClick={() => setGranularity("week")}
          >
            Week
          </button>
          <button
            className={granularity === "month" ? "pill active" : "pill"}
            onClick={() => setGranularity("month")}
          >
            Month
          </button>
        </div>
      </div>

      {/* 1. Deviation Rate Over Time */}
      <div className="chart-block">
        <h3>Deviation Rate Over Time</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart
            data={timeSeries}
            margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3e50" />
            <XAxis dataKey="period" stroke="#aaa" />
            <YAxis unit="%" stroke="#aaa" />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="yourDeviationRate"
              name="Your deviations %"
              stroke="#e74c3c"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="opponentLeftRate"
              name="Opponent left book %"
              stroke="#3498db"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 2. Opening Breakdown */}
      <div className="chart-block">
        <h3>Opening Breakdown (Top 15)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={openingBreakdown}
            margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3e50" />
            <XAxis
              dataKey="opening"
              stroke="#aaa"
              interval={0}
              angle={-30}
              textAnchor="end"
              height={70}
            />
            <YAxis stroke="#aaa" />
            <Tooltip />
            <Legend />
            <Bar
              dataKey="yourDev"
              stackId="a"
              name="Your deviations"
              fill="#e74c3c"
            />
            <Bar
              dataKey="oppLeft"
              stackId="a"
              name="Opponent left book"
              fill="#3498db"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 3. Move Number Distribution */}
      <div className="chart-block">
        <h3>Move Number Distribution</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart
            data={moveBuckets}
            margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3e50" />
            <XAxis dataKey="range" stroke="#aaa" />
            <YAxis stroke="#aaa" />
            <Tooltip />
            <Bar dataKey="count" name="# deviations" fill="#81b64c" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 4. Color Analysis */}
      <div className="chart-block">
        <h3>Color Analysis</h3>
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Tooltip />
            <Legend />
            <Pie
              data={colorPie}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label
            >
              {colorPie.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* 5. Variation Distribution per Opening */}
      <div className="chart-block">
        <h3>Variation Distribution per Opening (Top 12)</h3>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={variationByOpening}
            margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3e50" />
            <XAxis
              dataKey="opening"
              stroke="#aaa"
              interval={0}
              angle={-30}
              textAnchor="end"
              height={70}
            />
            <YAxis stroke="#aaa" />
            <Tooltip />
            <Legend />
            <Bar dataKey="v1" stackId="v" name="1 variation" fill="#81b64c" />
            <Bar dataKey="v2" stackId="v" name="2 variations" fill="#3498db" />
            <Bar dataKey="v3" stackId="v" name="3 variations" fill="#9b59b6" />
            <Bar
              dataKey="v4plus"
              stackId="v"
              name="4+ variations"
              fill="#f39c12"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 6. Chapter Distribution for Selected Opening */}
      <div className="chart-block">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            justifyContent: "space-between",
          }}
        >
          <h3 style={{ margin: 0 }}>
            Chapter Distribution — {selectedOpening || ""}
          </h3>
          <div>
            <label
              style={{ marginRight: 8, color: "#aaa", fontSize: "0.9rem" }}
            >
              Opening:
            </label>
            <select
              value={selectedOpening}
              onChange={(e) => setSelectedOpening(e.target.value)}
              style={{
                background: "#0f3460",
                color: "#eee",
                border: "1px solid #2c3e50",
                borderRadius: 6,
                padding: "0.35rem 0.5rem",
              }}
            >
              {openingOptions.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={chapterDistribution}
            layout="vertical"
            margin={{ top: 10, right: 20, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#2c3e50" />
            <XAxis type="number" stroke="#aaa" />
            <YAxis
              type="category"
              dataKey="chapter"
              stroke="#aaa"
              width={150}
            />
            <Tooltip />
            <Bar dataKey="count" name="# times played" fill="#81b64c" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
