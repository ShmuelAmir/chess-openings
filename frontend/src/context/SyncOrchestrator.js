/**
 * SyncOrchestrator - Manages the cache sync → analysis flow.
 *
 * This module provides an explicit event-based interface for the cache sync
 * workflow, decoupling the sync trigger (AuthContext) from the analysis
 * trigger (AnalysisPage).
 *
 * Events:
 * - 'cache-ready': Emitted when cache sync completes and games are available
 * - 'cache-cleared': Emitted when cache is cleared
 * - 'sync-error': Emitted when sync fails
 */

class SyncOrchestrator extends EventTarget {
  constructor() {
    super();
  }

  /**
   * Signal that cache sync has completed successfully.
   * Emits 'cache-ready' event to trigger downstream analysis.
   */
  notifyCacheReady() {
    const event = new CustomEvent("cache-ready", {
      detail: { timestamp: Date.now() },
    });
    this.dispatchEvent(event);
  }

  /**
   * Signal that cache has been cleared.
   * Emits 'cache-cleared' event to clear analysis results.
   */
  notifyCacheCleared() {
    const event = new CustomEvent("cache-cleared", {
      detail: { timestamp: Date.now() },
    });
    this.dispatchEvent(event);
  }

  /**
   * Signal that sync failed.
   * Emits 'sync-error' event with error details.
   */
  notifySyncError(error) {
    const event = new CustomEvent("sync-error", {
      detail: { error, timestamp: Date.now() },
    });
    this.dispatchEvent(event);
  }

  /**
   * Subscribe to a sync orchestrator event.
   *
   * Usage:
   *   syncOrchestrator.on("cache-ready", () => {
   *     analyzeGames();
   *   });
   *
   * @param {string} eventName - Event name ('cache-ready', 'cache-cleared', 'sync-error')
   * @param {Function} listener - Callback function
   */
  on(eventName, listener) {
    this.addEventListener(eventName, listener);
  }

  /**
   * Unsubscribe from a sync orchestrator event.
   */
  off(eventName, listener) {
    this.removeEventListener(eventName, listener);
  }
}

// Singleton instance
export const syncOrchestrator = new SyncOrchestrator();
