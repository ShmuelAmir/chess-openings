import type {
  ApiErrorBody,
  Backend,
  DrillAttempt,
  DrillAttemptRecorded,
  GameFilters,
  RecallGap,
  RecallView,
  SyncState,
} from "./backend";

interface RequestOptions {
  method?: "GET" | "POST";
  body?: DrillAttempt;
  failure: string;
  rateLimit?: string;
}

/**
 * The HTTP backend adapter: the backend's calls for one account, each
 * resolving with the response body or rejecting with an Error whose message
 * is fit to show the user.
 */
export function createHttpBackend({
  lichessToken,
  chessComUsername,
}: {
  lichessToken: string;
  chessComUsername: string;
}): Backend {
  // The backend's reason for a failed response, else the call's own wording.
  // `rateLimit` is what to say instead when Lichess rate-limited the call.
  // `body` is sent as JSON. `T` is what the API returns; nothing checks it.
  async function request<T>(
    path: string,
    { method = "GET", body, failure, rateLimit }: RequestOptions,
  ): Promise<T> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${lichessToken}`,
    };
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, {
      method,
      headers,
      body: body && JSON.stringify(body),
    });
    if (!response.ok) {
      const data: ApiErrorBody = await response.json().catch(() => ({}));
      throw new Error(
        (response.status === 429 && rateLimit) || data.detail || failure,
      );
    }
    return response.json();
  }

  const syncPath = `/api/sync?${new URLSearchParams({ chess_com_username: chessComUsername })}`;

  // The Game Filters as query parameters
  function filterParams(filters: GameFilters) {
    const params = new URLSearchParams({
      chess_com_username: chessComUsername,
      date_range: filters.dateRange,
      rated_only: String(filters.ratedOnly),
    });
    filters.timeClasses.forEach((tc) => params.append("time_classes", tc));
    filters.studies.forEach((id) => params.append("studies", id));
    return params;
  }

  return {
    readSyncState: () =>
      request<SyncState>(syncPath, { failure: "Sync failed" }),
    startSync: () =>
      request<SyncState>(syncPath, { method: "POST", failure: "Sync failed" }),
    loadRecallView: (filters) =>
      request<RecallView>(`/api/recall-view?${filterParams(filters)}`, {
        failure: "Could not load Recall Gaps",
        rateLimit:
          "Lichess rate limit reached. Please wait a minute and try again.",
      }),
    loadPracticeQueue: async (filters) =>
      (
        await request<{ gaps: RecallGap[] }>(
          `/api/practice-session?${filterParams(filters)}`,
          { failure: "Could not load the practice session" },
        )
      ).gaps,
    recordDrillAttempt: (attempt) =>
      request<DrillAttemptRecorded>("/api/drill-attempts", {
        method: "POST",
        body: attempt,
        failure: "Could not save the attempt",
      }),
  };
}
