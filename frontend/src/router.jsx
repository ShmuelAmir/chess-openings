import {
  createRouter,
  createRootRoute,
  createRoute,
  Outlet,
} from "@tanstack/react-router";
import Layout from "./components/Layout";
import RecallPage from "./pages/RecallPage";
import OpeningDistributionPage from "./pages/OpeningDistributionPage";
import SettingsPage from "./pages/SettingsPage";

// Root route with Layout wrapper
const rootRoute = createRootRoute({
  component: Layout,
});

// Recall view: the ranked Recall Gaps
const recallRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: RecallPage,
});

// Opening distribution page (new page)
const openingDistributionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/openings",
  component: OpeningDistributionPage,
});

// Settings: the "not repertoire" exclusion list
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsPage,
});

// Create the route tree
const routeTree = rootRoute.addChildren([
  recallRoute,
  openingDistributionRoute,
  settingsRoute,
]);

// Create and export the router
export const router = createRouter({ routeTree });
