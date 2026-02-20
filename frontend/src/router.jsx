import {
  createRouter,
  createRootRoute,
  createRoute,
  Outlet,
} from "@tanstack/react-router";
import Layout from "./components/Layout";
import AnalysisPage from "./pages/AnalysisPage";
import OpeningDistributionPage from "./pages/OpeningDistributionPage";

// Root route with Layout wrapper
const rootRoute = createRootRoute({
  component: Layout,
});

// Analysis page (original functionality)
const analysisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: AnalysisPage,
});

// Opening distribution page (new page)
const openingDistributionRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/openings",
  component: OpeningDistributionPage,
});

// Create the route tree
const routeTree = rootRoute.addChildren([
  analysisRoute,
  openingDistributionRoute,
]);

// Create and export the router
export const router = createRouter({ routeTree });
