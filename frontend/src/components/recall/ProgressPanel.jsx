import { formatMissRate, missRateRuns } from "./format";

// The Miss Depth rows, as the backend counts them: the user's 2nd move first,
// the last also holding every later move
const DEPTH_LABELS = ["2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10+"];
const FIRST_DEPTH = 2;

const CHART_WIDTH = 300;
const CHART_HEIGHT = 90;
const PAD = { top: 8, right: 6, bottom: 4, left: 30 };

/** "2026-03" as its month's initial: "M". */
function monthInitial(month) {
  return new Date(`${month}-01T00:00:00Z`).toLocaleString("en", { month: "narrow", timeZone: "UTC" });
}

/** "2026-03" as "Mar 2026". */
function monthName(month) {
  return new Date(`${month}-01T00:00:00Z`).toLocaleString("en", {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/**
 * The Progress panel: the monthly Miss Rate and Miss Depth over the last 12
 * months, under every Game Filter but the date range. See Miss Depth in
 * GLOSSARY.md.
 */
export default function ProgressPanel({ trend, studyNames, onClose }) {
  return (
    <section className="rv-detail rv-progress">
      <div className="rv-progress-head">
        <strong>Progress</strong>
        <button className="rv-link" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="rv-muted">
        {studyNames.length > 0 ? studyNames.join(", ") : "All studies"} · last {trend.length} months
      </div>

      <div className="rv-label">Miss Rate</div>
      <MissRateChart trend={trend} />

      <div className="rv-label">Miss Depth: the move you went wrong on</div>
      <MissDepthGrid trend={trend} />
      <div className="rv-muted rv-progress-note">
        Misses moving down the grid means you are getting further into your lines.
        The outlined cell is the month's median (3+ misses).
      </div>
    </section>
  );
}

function MissRateChart({ trend }) {
  const plotW = CHART_WIDTH - PAD.left - PAD.right;
  const plotH = CHART_HEIGHT - PAD.top - PAD.bottom;
  const step = trend.length > 1 ? plotW / (trend.length - 1) : 0;
  const points = trend.map((m, i) => ({
    ...m,
    x: PAD.left + i * step,
    y: m.miss_rate === null ? null : PAD.top + (1 - m.miss_rate) * plotH,
  }));

  const segments = missRateRuns(points);

  return (
    <svg
      className="rv-progress-chart"
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      role="img"
      aria-label="Miss Rate by month over the last 12 months"
    >
      {[0, 0.5, 1].map((v) => {
        const y = PAD.top + (1 - v) * plotH;
        return (
          <g key={v} className="rv-progress-grid">
            <line x1={PAD.left} x2={CHART_WIDTH - PAD.right} y1={y} y2={y} />
            <text x={PAD.left - 6} y={y} dominantBaseline="middle" textAnchor="end">
              {Math.round(v * 100)}%
            </text>
          </g>
        );
      })}
      {segments.map((seg) => (
        <polyline key={seg[0].month} points={seg.map((p) => `${p.x},${p.y}`).join(" ")} />
      ))}
      {points.map((p) => (
        <g key={p.month}>
          {p.y !== null && <circle cx={p.x} cy={p.y} r={3} />}
          <rect
            x={p.x - step / 2}
            y={0}
            width={step || plotW}
            height={CHART_HEIGHT}
            fill="transparent"
          >
            <title>
              {`${monthName(p.month)}: ${
                p.miss_rate === null
                  ? `${p.games} ${p.games === 1 ? "game" : "games"} (too few for a Miss Rate)`
                  : `${formatMissRate(p.miss_rate)} of ${p.games} games`
              }`}
            </title>
          </rect>
        </g>
      ))}
    </svg>
  );
}

function MissDepthGrid({ trend }) {
  const max = Math.max(1, ...trend.flatMap((m) => m.miss_depths));
  const totals = trend.map((m) => m.miss_depths.reduce((a, b) => a + b, 0));
  return (
    <div className="rv-depth" style={{ gridTemplateColumns: `2.2rem repeat(${trend.length}, 1fr)` }}>
      {DEPTH_LABELS.map((label, row) => (
        <DepthRow key={label} label={label} row={row} trend={trend} totals={totals} max={max} />
      ))}
      <span />
      {trend.map((m) => (
        <span key={m.month} className="rv-depth-month" title={monthName(m.month)}>
          {monthInitial(m.month)}
        </span>
      ))}
    </div>
  );
}

function DepthRow({ label, row, trend, totals, max }) {
  return (
    <>
      <span className="rv-depth-label">{label}</span>
      {trend.map((m, i) => {
        const count = m.miss_depths[row];
        const median =
          m.median_miss_depth !== null &&
          Math.min(m.median_miss_depth, FIRST_DEPTH + DEPTH_LABELS.length - 1) - FIRST_DEPTH === row;
        const total = totals[i];
        // How strongly the cell is shaded: by its count against the busiest cell
        const heat = count ? 0.2 + 0.8 * (count / max) : 0;
        return (
          <span
            key={m.month}
            className={`rv-depth-cell${count ? " hit" : ""}${heat > 0.55 ? " strong" : ""}${
              median ? " median" : ""
            }`}
            style={count ? { "--heat": heat } : undefined}
            title={`${monthName(m.month)}, your ${label} move: ${count} of ${total} ${
              total === 1 ? "miss" : "misses"
            }${median ? " (median)" : ""}`}
          >
            {count || ""}
          </span>
        );
      })}
    </>
  );
}
