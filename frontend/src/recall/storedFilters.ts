import type { DateRange, GameFilters, TimeClass } from "../backend/backend";

const STORAGE_KEY = "recall-view.game-filters";

export const TIME_CLASSES: TimeClass[] = ["bullet", "blitz", "rapid", "daily"];

export const DATE_RANGES: { id: DateRange; label: string }[] = [
  { id: "month", label: "Last month" },
  { id: "3months", label: "Last 3 months" },
  { id: "year", label: "Last year" },
  { id: "all", label: "All time" },
];

export const DEFAULT_FILTERS: GameFilters = {
  timeClasses: ["blitz", "rapid"],
  dateRange: "3months",
  ratedOnly: true,
  studies: [], // nothing selected means all studies
};

const isStringList = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const isTimeClassList = (value: unknown): value is TimeClass[] =>
  isStringList(value) &&
  // Widened so `includes` takes any string: finding it is what makes it a TimeClass
  value.every((tc) => (TIME_CLASSES as string[]).includes(tc));

const isDateRange = (value: unknown): value is DateRange =>
  DATE_RANGES.some((range) => range.id === value);

/** The Game Filters remembered in this browser; defaults for anything missing or invalid. */
export function loadFilters(): GameFilters {
  let parsed: unknown;
  try {
    const item = localStorage.getItem(STORAGE_KEY);
    parsed = item === null ? null : JSON.parse(item);
  } catch {
    return DEFAULT_FILTERS;
  }
  if (!parsed || typeof parsed !== "object") return DEFAULT_FILTERS;
  // An old or corrupt value may have any of these fields, of any type
  const stored: Partial<Record<keyof GameFilters, unknown>> = parsed;

  return {
    timeClasses: isTimeClassList(stored.timeClasses)
      ? stored.timeClasses
      : DEFAULT_FILTERS.timeClasses,
    dateRange: isDateRange(stored.dateRange)
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
export function saveFilters(filters: GameFilters): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  } catch {
    // Storage unavailable (private mode, quota, blocked): keep working without it
  }
}
