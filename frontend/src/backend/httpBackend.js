/**
 * The HTTP backend adapter: the backend's calls for one account, each
 * resolving with the response body or rejecting with an Error whose message
 * is fit to show the user.
 */
export function createHttpBackend({ lichessToken, chessComUsername }) {
  // The backend's reason for a failed response, else the call's own wording.
  // `rateLimit` is what to say instead when Lichess rate-limited the call.
  // `body` is sent as JSON.
  async function request(path, { method = "GET", body, failure, rateLimit }) {
    const headers = { Authorization: `Bearer ${lichessToken}` };
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, {
      method,
      headers,
      body: body && JSON.stringify(body),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(
        (response.status === 429 && rateLimit) || data.detail || failure,
      );
    }
    return response.json();
  }

  const syncPath = `/api/sync?${new URLSearchParams({ chess_com_username: chessComUsername })}`;

  // The Game Filters as query parameters
  function filterParams(filters) {
    const params = new URLSearchParams({
      chess_com_username: chessComUsername,
      date_range: filters.dateRange,
      rated_only: filters.ratedOnly,
    });
    filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
    filters.studies.forEach((id) => params.append("studies", id));
    return params;
  }

  return {
    /** The Sync state, as GET /api/sync reports it. */
    readSyncState: () => request(syncPath, { failure: "Sync failed" }),
    /** Start a Sync; resolves with the Sync state. */
    startSync: () => request(syncPath, { method: "POST", failure: "Sync failed" }),
    /** The recall view under the Game Filters, as GET /api/recall-view reports it. */
    loadRecallView: (filters) =>
      request(`/api/recall-view?${filterParams(filters)}`, {
        failure: "Could not load Recall Gaps",
        rateLimit: "Lichess rate limit reached. Please wait a minute and try again.",
      }),
    /** The practice-session queue under the Game Filters: the due Open Recall Gaps, in ranking order. */
    loadPracticeQueue: async (filters) =>
      (
        await request(`/api/practice-session?${filterParams(filters)}`, {
          failure: "Could not load the practice session",
        })
      ).gaps,
    /** Record a finished Drill Attempt. */
    recordDrillAttempt: (attempt) =>
      request("/api/drill-attempts", {
        method: "POST",
        body: attempt,
        failure: "Could not save the attempt",
      }),
  };
}
