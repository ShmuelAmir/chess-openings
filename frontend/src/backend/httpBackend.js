/**
 * The HTTP backend adapter: the backend's calls for one account, each
 * resolving with the response body or rejecting with an Error whose message
 * is fit to show the user.
 */
export function createHttpBackend({ lichessToken, chessComUsername }) {
  // The backend's reason for a failed response, else the call's own wording
  async function request(path, { method = "GET", failure }) {
    const response = await fetch(path, {
      method,
      headers: { Authorization: `Bearer ${lichessToken}` },
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || failure);
    }
    return response.json();
  }

  const syncPath = `/api/sync?${new URLSearchParams({ chess_com_username: chessComUsername })}`;

  return {
    /** The Sync state, as GET /api/sync reports it. */
    readSyncState: () => request(syncPath, { failure: "Sync failed" }),
    /** Start a Sync; resolves with the Sync state. */
    startSync: () => request(syncPath, { method: "POST", failure: "Sync failed" }),
  };
}
