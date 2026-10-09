import { TIME_CLASSES, DATE_RANGES } from "../../recall/storedFilters";

const COLORS = [
  { id: "white", label: "White" },
  { id: "black", label: "Black" },
];

/**
 * The Game Filters of the recall view, as a sticky rail. The Study filter
 * stands in for a Color filter: color follows from the selected studies.
 * `disabled` during practice, when the Game Filters cannot be changed.
 */
export default function FilterRail({ filters, studies, disabled, onChange }) {
  const set = (patch) => onChange({ ...filters, ...patch });

  const toggleStudy = (id) =>
    set({
      studies: filters.studies.includes(id)
        ? filters.studies.filter((s) => s !== id)
        : [...filters.studies, id],
    });

  // All of a color's studies selected -> none of them; otherwise -> all of them
  const toggleColor = (ids) => {
    const allOn = ids.every((id) => filters.studies.includes(id));
    const others = filters.studies.filter((id) => !ids.includes(id));
    set({ studies: allOn ? others : [...others, ...ids] });
  };

  // No study selected means all of them
  const noStudySelected = filters.studies.length === 0;

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
      <fieldset className="rv-rail-fields" disabled={disabled}>
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

        <div className="rv-rail-section">
          <div className="rv-rail-head">
            <span className="rv-rail-title">Studies</span>
            {!noStudySelected && (
              <button
                type="button"
                className="rv-link"
                onClick={() => set({ studies: [] })}
              >
                clear
              </button>
            )}
          </div>
          {COLORS.map((color) => {
            const group = studies.filter((study) => study.color === color.id);
            if (group.length === 0) return null;
            const ids = group.map((study) => study.id);
            const allOn = ids.every((id) => filters.studies.includes(id));
            return (
              <div key={color.id} className="rv-study-group">
                <div className="rv-rail-head">
                  <span className="rv-label">
                    {color.label}
                    <span className={`rv-dot ${color.id}`} />
                  </span>
                  <button
                    type="button"
                    className="rv-link"
                    onClick={() => toggleColor(ids)}
                  >
                    {allOn ? "none" : "all"}
                  </button>
                </div>
                <div className="rv-pills">
                  {group.map((study) => (
                    <button
                      key={study.id}
                      type="button"
                      title={study.name}
                      className={
                        filters.studies.includes(study.id)
                          ? "rv-pill on"
                          : noStudySelected
                            ? "rv-pill implicit"
                            : "rv-pill"
                      }
                      onClick={() => toggleStudy(study.id)}
                    >
                      {study.opening_name || study.name}
                      <span className="rv-badge">{study.gaps}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </fieldset>
    </aside>
  );
}
