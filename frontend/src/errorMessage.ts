/**
 * The message of a caught error, fit to show the user. The app, fetch and the
 * Backend throw only Errors; anything else thrown is shown as text.
 */
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
