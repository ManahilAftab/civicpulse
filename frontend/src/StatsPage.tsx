import { useEffect, useState } from "react"
import { getStats, type Stats } from "./api/client"

function CountGroup({ title, values }: { title: string; values: Record<string, number> }) {
  return <section className="card stat-group"><h2>{title}</h2>{Object.entries(values).map(([label, count]) => <div className="stat-row" key={label}><span>{label.replace("_", " ")}</span><strong>{count}</strong></div>)}</section>
}

export function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [cache, setCache] = useState("")
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError("")
    getStats(controller.signal)
      .then((result) => { setStats(result.data); setCache(result.cache) })
      .catch((caught: Error) => { if (caught.name !== "AbortError") setError(caught.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [revision])

  return (
    <main className="page">
      <div className="page-heading"><div><p className="eyebrow">Overview</p><h1>CivicPulse statistics</h1></div><button type="button" className="secondary" onClick={() => setRevision((value) => value + 1)}>Refresh</button></div>
      {loading && <p role="status">Loading statistics…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {stats && <><section className="card total-stat"><span>Total complaints</span><strong>{stats.total}</strong><small>Cache: {cache}</small></section><div className="stats-grid"><CountGroup title="By category" values={stats.by_category} /><CountGroup title="By priority" values={stats.by_priority} /><CountGroup title="By status" values={stats.by_status} /></div></>}
    </main>
  )
}
