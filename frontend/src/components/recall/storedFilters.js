const STORAGE_KEY = "recall-view.game-filters";

const TIME_CLASSES = ["bullet", "blitz", "rapid", "daily"];
const DATE_RANGES = ["month", "3months", "year", "all"];

export const DEFAULT_FILTERS = {
  timeClasses: ["blitz", "rapid"],
  dateRange: "3months",
  ratedOnly: true,
  studies: [], // nothing selected means all studies
};

const isStringList = (value) =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

/** The Game Filters remembered in this browser; defaults for anything missing or invalid. */
export function loadFilters() {
  let stored;
  try {
    stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    return DEFAULT_FILTERS;
  }
  if (!stored || typeof stored !== "object") return DEFAULT_FILTERS;

  return {
    timeClasses:
      isStringList(stored.timeClasses) &&
      stored.timeClasses.every((tc) => TIME_CLASSES.includes(tc))
        ? stored.timeClasses
        : DEFAULT_FILTERS.timeClasses,
    dateRange: DATE_RANGES.includes(stored.dateRange)
      ? stored.dateRange
      : DEFAULT_FILTERS.dateRange,
    ratedOnly:
      typeof stored.ratedOnly === "boolean"
        ? stored.ratedOnly
        : DEFAULT_FILTERS.ratedOnly,
    studies: isStringList(stored.studies)
      ? stored.studies
      : DEFAULT_FILTERS.studies,
  };
}

/** Remember the Game Filters in this browser; a storage failure only loses the memory. */
export function saveFilters(filters) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  } catch {
    // Storage unavailable (private mode, quota, blocked): keep working without it
  }
}
