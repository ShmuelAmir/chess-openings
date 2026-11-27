import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { router } from "./router";
import { SampleAccountContext } from "./context/SampleAccountContext";
import type { SampleAccount } from "./sample/sampleAccount";
import "./index.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("index.html has no #root element");
const root = ReactDOM.createRoot(rootElement);

function render(sampleAccount: SampleAccount | null) {
  root.render(
    <React.StrictMode>
      <SampleAccountContext.Provider value={sampleAccount}>
        <RouterProvider router={router} />
      </SampleAccountContext.Provider>
    </React.StrictMode>,
  );
}

// Only the sample mode loads the sample account; every other build drops
// this import, so the sample data never reaches the production bundle
if (import.meta.env.MODE === "sample") {
  import("./sample/sampleAccount").then(({ createSampleAccount }) =>
    render(createSampleAccount()),
  );
} else {
  render(null);
}
