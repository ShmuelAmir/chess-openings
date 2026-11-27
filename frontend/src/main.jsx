import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { router } from "./router";
import { SampleAccountContext } from "./context/SampleAccountContext";
import "./index.css";

// Only the sample mode loads the sample account; every other build drops
// this import, so the sample data never reaches the production bundle
const sampleAccount =
  import.meta.env.MODE === "sample"
    ? import("./sample/sampleAccount").then(({ createSampleAccount }) => createSampleAccount())
    : Promise.resolve(null);

sampleAccount.then((account) => {
  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <SampleAccountContext.Provider value={account}>
        <RouterProvider router={router} />
      </SampleAccountContext.Provider>
    </React.StrictMode>,
  );
});
