const TIME_CLASSES = ["bullet", "blitz", "rapid", "daily"];

const DATE_RANGES = [
  { id: "month", label: "Last month" },
  { id: "3months", label: "Last 3 months" },
  { id: "year", label: "Last year" },
  { id: "all", label: "All time" },
];

/** The Game Filters of the recall view, as a sticky rail. */
export default function FilterRail({ filters, onChange }) {
  const set = (patch) => onChange({ ...filters, ...patch });

  const toggleTimeClass = (tc) =>
    set({
      timeClasses: filters.timeClasses.includes(tc)
        ? filters.timeClasses.filter((t) => t !== tc)
        : [...filters.timeClasses, tc],
    });

  // No time control selected means all of them
  const noneSelected = filters.timeClasses.length === 0;

  return (
    <aside className="rv-rail">
      <div className="rv-rail-section">
        <div className="rv-rail-title">Games</div>
        <div className="rv-seg">
          {TIME_CLASSES.map((tc) => (
            <button
              key={tc}
              type="button"
              className={
                filters.timeClasses.includes(tc)
                  ? "on"
                  : noneSelected
                    ? "implicit"
                    : ""
              }
              onClick={() => toggleTimeClass(tc)}
            >
              {tc}
            </button>
          ))}
        </div>
        <select
          className="rv-select"
          value={filters.dateRange}
          onChange={(e) => set({ dateRange: e.target.value })}
        >
          {DATE_RANGES.map((range) => (
            <option key={range.id} value={range.id}>
              {range.label}
            </option>
          ))}
        </select>
        <label className="rv-switch">
          <input
            type="checkbox"
            checked={filters.ratedOnly}
            onChange={() => set({ ratedOnly: !filters.ratedOnly })}
          />
          <span className="rv-switch-track" />
          Rated only
        </label>
      </div>
    </aside>
  );
}
