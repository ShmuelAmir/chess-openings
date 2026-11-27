import type { TrendMonth } from "../../backend/backend";
import { missRateRuns } from "./format";

const WIDTH = 96;
const HEIGHT = 20;
const PAD = 2;

/**
 * The monthly Miss Rate trend as a sparkline, oldest month on the left.
 * Months without a Miss Rate (too few games) are gaps in the line.
 */
export default function Sparkline({ trend }: { trend: TrendMonth[] }) {
  if (trend.length === 0) return null;
  const step = trend.length > 1 ? (WIDTH - 2 * PAD) / (trend.length - 1) : 0;
  const points = trend.map((m, i) => ({
    ...m,
    x: PAD + i * step,
    // A higher Miss Rate sits higher
    y:
      m.miss_rate === null
        ? null
        : HEIGHT - PAD - m.miss_rate * (HEIGHT - 2 * PAD),
  }));

  const segments = missRateRuns(points);

  return (
    <svg
      className="rv-spark"
      width={WIDTH}
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="Miss Rate over the last 12 months"
    >
      <line
        className="rv-spark-base"
        x1={PAD}
        x2={WIDTH - PAD}
        y1={HEIGHT - PAD}
        y2={HEIGHT - PAD}
      />
      {segments.map((seg) => (
        <polyline
          key={seg[0].month}
          points={seg.map((p) => `${p.x},${p.y}`).join(" ")}
        />
      ))}
      {points.map((p) => (
        <g key={p.month}>
          {p.y !== null && <circle cx={p.x} cy={p.y} r={1.5} />}
          {/* A full-height hover target per month */}
          <rect
            x={p.x - step / 2}
            y={0}
            width={step || WIDTH}
            height={HEIGHT}
            fill="transparent"
          >
            <title>
              {p.month}:{" "}
              {p.miss_rate === null
                ? `${p.games} ${p.games === 1 ? "game" : "games"} (too few)`
                : `${Math.round(p.miss_rate * 100)}% · ${p.games} games`}
            </title>
          </rect>
        </g>
      ))}
    </svg>
  );
}
