import { useState } from "react"
import { Dashboard } from "./Dashboard"
import { StatsPage } from "./StatsPage"
import { SubmitPage } from "./SubmitPage"
import "./App.css"

type View = "submit" | "dashboard" | "stats"

export default function App() {
  const [view, setView] = useState<View>("submit")
  return (
    <div className="app-shell">
      <header className="site-header"><button className="brand" type="button" onClick={() => setView("submit")}>CivicPulse</button><nav aria-label="Primary navigation">{(["submit", "dashboard", "stats"] as View[]).map((item) => <button type="button" key={item} aria-pressed={view === item} onClick={() => setView(item)}>{item === "submit" ? "Submit" : item[0].toUpperCase() + item.slice(1)}</button>)}</nav></header>
      {view === "submit" && <SubmitPage />}
      {view === "dashboard" && <Dashboard />}
      {view === "stats" && <StatsPage />}
    </div>
  )
}
