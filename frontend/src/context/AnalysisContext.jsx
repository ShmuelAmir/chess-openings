import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";
import { useAuth } from "./AuthContext";

const AnalysisContext = createContext(null);

export function AnalysisProvider({ children }) {
  const { lichessToken, chessComUsername } = useAuth();

  // Studies state
  const [studies, setStudies] = useState([]);
  const [selectedStudies, setSelectedStudies] = useState([]);
  const [studiesLoading, setStudiesLoading] = useState(false);

  // Analysis results
  const [results, setResults] = useState(null);
  const [totalGames, setTotalGames] = useState(0);
  const [matchedGames, setMatchedGames] = useState(0);

  // Analysis UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeFilters, setActiveFilters] = useState(null);

  // Layout UI state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Debounce timer ref for auto-analysis
  const debounceRef = useRef(null);

  /**
   * Fetch studies from Lichess.
   * Called when user logs in or manually refreshes.
   */
  const fetchStudies = useCallback(async () => {
    if (!lichessToken) return;

    setStudiesLoading(true);
    try {
      const response = await fetch("/api/lichess/studies", {
        headers: { Authorization: `Bearer ${lichessToken}` },
      });

      if (!response.ok) {
        throw new Error("Failed to fetch studies");
      }

      const data = await response.json();
      setStudies(data.studies || []);
    } catch (err) {
      console.error("Failed to fetch studies:", err);
      setError(err.message);
    } finally {
      setStudiesLoading(false);
    }
  }, [lichessToken]);

  /**
   * Update selected studies.
   * Triggers auto-analysis if cacheStatus allows.
   */
  const selectStudies = useCallback((studyIds) => {
    setSelectedStudies(studyIds);

    // Clear results if no studies selected
    if (studyIds.length === 0) {
      setResults(null);
      setTotalGames(0);
      setMatchedGames(0);
      return;
    }
  }, []);

  /**
   * Run analysis with given filters.
   * Called explicitly when user clicks "Apply Filters".
   */
  const analyzeGames = useCallback(
    async (filters = null) => {
      if (!chessComUsername || !lichessToken) {
        setError("Please connect both accounts first");
        return;
      }

      if (selectedStudies.length === 0) {
        setError("Please select at least one study");
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const currentDate = new Date();
        const nowTs = Math.floor(Date.now() / 1000);
        const weekAgoTs = nowTs - 7 * 24 * 60 * 60;
        const weekAgoDate = new Date(weekAgoTs * 1000);

        // Use provided filters or fall back to active filters or defaults
        const defaultFilters =
          filters ||
          activeFilters || {
            fromYear: weekAgoDate.getFullYear(),
            fromMonth: weekAgoDate.getMonth() + 1,
            toYear: currentDate.getFullYear(),
            toMonth: currentDate.getMonth() + 1,
            fromTimestamp: weekAgoTs,
            toTimestamp: nowTs,
            timeClasses: ["rapid"],
            colorFilter: "both",
            ratedOnly: true,
          };

        const params = new URLSearchParams({
          chess_com_username: chessComUsername,
          from_year: defaultFilters.fromYear,
          from_month: defaultFilters.fromMonth,
          to_year: defaultFilters.toYear,
          to_month: defaultFilters.toMonth,
        });

        if (defaultFilters.fromTimestamp) {
          params.append("from_ts", defaultFilters.fromTimestamp);
        }
        if (defaultFilters.toTimestamp) {
          params.append("to_ts", defaultFilters.toTimestamp);
        }

        selectedStudies.forEach((id) => params.append("study_ids", id));

        const selectedStudyNames = studies
          .filter((s) => selectedStudies.includes(s.id))
          .map((s) => s.name);
        selectedStudyNames.forEach((name) =>
          params.append("study_names", name),
        );

        if (
          defaultFilters.timeClasses &&
          defaultFilters.timeClasses.length > 0
        ) {
          defaultFilters.timeClasses.forEach((tc) =>
            params.append("time_classes", tc),
          );
        }

        if (defaultFilters.ratedOnly) {
          params.append("rated", "true");
        }

        if (
          defaultFilters.colorFilter &&
          defaultFilters.colorFilter !== "both"
        ) {
          params.append("color", defaultFilters.colorFilter);
        }

        const response = await fetch(`/api/analyze?${params}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${lichessToken}` },
        });

        if (!response.ok) {
          throw new Error("Analysis failed");
        }

        const data = await response.json();
        setResults(data.results);
        setTotalGames(data.total_games || 0);
        setMatchedGames(data.filtered_by_opening || 0);
        setActiveFilters(defaultFilters);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [chessComUsername, lichessToken, selectedStudies, studies, activeFilters],
  );

  /**
   * Clear all analysis state.
   */
  const clearResults = useCallback(() => {
    setResults(null);
    setTotalGames(0);
    setMatchedGames(0);
    setActiveFilters(null);
    setError(null);
  }, []);

  const value = {
    // Studies
    studies,
    selectedStudies,
    studiesLoading,
    fetchStudies,
    selectStudies,

    // Analysis results
    results,
    totalGames,
    matchedGames,

    // Analysis UI state
    loading,
    error,
    activeFilters,
    analyzeGames,
    clearResults,

    // Layout UI state
    sidebarCollapsed,
    setSidebarCollapsed,

    // Internal (for auto-analysis coordination)
    debounceRef,
  };

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error("useAnalysis must be used within an AnalysisProvider");
  }
  return context;
}
