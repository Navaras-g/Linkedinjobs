// @ts-ignore - React types are not configured in this TS starter scaffold.
import { createElement } from "react";
// @ts-ignore - React DOM types are not configured in this TS starter scaffold.
import { createRoot } from "react-dom/client";

// @ts-ignore - Importing JSX module from TypeScript entrypoint.
import App from "./App.jsx";
import "./style.css";

const rootElement = document.getElementById("app");
if (!rootElement) {
  throw new Error("Root element '#app' not found");
}

createRoot(rootElement).render(createElement(App));
