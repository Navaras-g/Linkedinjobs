import { useState } from "react";

import DashboardPage from "./pages/DashboardPage";
import SettingsPage from "./pages/SettingsPage";

function App() {
  const [page, setPage] = useState("dashboard");

  return (
    <>
      <nav>
        <button type="button" onClick={() => setPage("dashboard")} disabled={page === "dashboard"}>
          Dashboard
        </button>
        <button type="button" onClick={() => setPage("settings")} disabled={page === "settings"}>
          Settings
        </button>
      </nav>
      {page === "dashboard" ? <DashboardPage /> : <SettingsPage />}
    </>
  );
}

export default App;
