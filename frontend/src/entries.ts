/** `Object.entries` of a record, keeping its key type. */
export function entries<K extends string, V>(record: Record<K, V>): [K, V][] {
  // Object.entries widens the keys to string; a record's keys are its K
  return Object.entries(record) as [K, V][];
}
