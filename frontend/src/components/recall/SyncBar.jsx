import { formatAgo } from "./format";

const SOURCE_NAMES = { chess_com: "Chess.com", lichess: "Lichess" };

/** The Sync state above the list: last synced, the Sync button, failed sources. */
export default function SyncBar({ status, syncing, error, onSync }) {
  const failed = status
    ? Object.entries(status.sources).filter(([, source]) => source.status === "failed")
    : [];

  return (
    <div className="rv-syncbar">
      <div className="rv-syncline">
        <span className="rv-muted">
          {syncing
            ? (status?.progress ?? "Syncing…")
            : status?.last_synced_at
              ? `Last synced ${formatAgo(status.last_synced_at)}`
              : "Not synced yet"}
        </span>
        <button type="button" className="rv-link" onClick={onSync} disabled={syncing}>
          Sync
        </button>
      </div>

      {!syncing && (failed.length > 0 || error) && (
        <div className="rv-syncfail">
          <span>
            {error ||
              failed
                .map(([key, source]) => `${SOURCE_NAMES[key]} sync failed: ${source.error}`)
                .join(" · ")}
          </span>
          <button type="button" className="rv-link" onClick={onSync}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
