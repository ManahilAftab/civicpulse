import { useEffect, useState } from "react"
import { getComplaints, updateStatus, type Complaint, type ComplaintPage } from "./api/client"

const categories = ["water", "electricity", "sanitation", "roads", "streetlights", "other"]
const priorities = ["high", "normal", "low"]
const statuses = ["open", "in_progress", "resolved", "rejected"]

function StatusEditor({ complaint, onUpdated }: { complaint: Complaint; onUpdated: () => void }) {
  const [selected, setSelected] = useState(complaint.status)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function save() {
    setBusy(true)
    setError("")
    try {
      await updateStatus(complaint.id, selected)
      onUpdated()
    } catch (caught) {
      setError((caught as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="status-editor">
      <select aria-label="New status" value={selected} onChange={(event) => setSelected(event.target.value)} disabled={busy}>
        {statuses.map((status) => <option key={status} value={status}>{status.replace("_", " ")}</option>)}
      </select>
      <button type="button" onClick={save} disabled={busy || selected === complaint.status}>{busy ? "Saving…" : "Update"}</button>
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  )
}

export function Dashboard() {
  const [category, setCategory] = useState("")
  const [priority, setPriority] = useState("")
  const [status, setStatus] = useState("")
  const [page, setPage] = useState(1)
  const [revision, setRevision] = useState(0)
  const [data, setData] = useState<ComplaintPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams({ page: String(page), page_size: "10" })
    if (category) params.set("category", category)
    if (priority) params.set("priority", priority)
    if (status) params.set("status", status)
    setLoading(true)
    setError("")
    getComplaints(params, controller.signal)
      .then(setData)
      .catch((caught: Error) => {
        if (caught.name !== "AbortError") setError(caught.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [category, priority, status, page, revision])

  function changeFilter(setter: (value: string) => void, value: string) {
    setter(value)
    setPage(1)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <main className="page">
      <div className="page-heading">
        <div><p className="eyebrow">Operations</p><h1>Complaint dashboard</h1></div>
        <button type="button" className="secondary" onClick={() => setRevision((value) => value + 1)}>Refresh</button>
      </div>

      <section className="card filters" aria-label="Complaint filters">
        <label>Category<select value={category} onChange={(event) => changeFilter(setCategory, event.target.value)}><option value="">All</option>{categories.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Priority<select value={priority} onChange={(event) => changeFilter(setPriority, event.target.value)}><option value="">All</option>{priorities.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label>Status<select value={status} onChange={(event) => changeFilter(setStatus, event.target.value)}><option value="">All</option>{statuses.map((value) => <option key={value} value={value}>{value.replace("_", " ")}</option>)}</select></label>
      </section>

      {loading && <p role="status">Loading complaints…</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {!loading && data?.items.length === 0 && <section className="card"><p>No complaints match these filters.</p></section>}

      <div className="complaint-list">
        {data?.items.map((complaint) => (
          <article className="card complaint" key={`${complaint.id}-${complaint.updated_at}`}>
            <div className="badges"><span>{complaint.category}</span><span>{complaint.priority}</span><span>{complaint.status.replace("_", " ")}</span></div>
            <h2>{complaint.ai_summary || complaint.text}</h2>
            <p>{complaint.text}</p>
            <p className="meta"><strong>Location:</strong> {complaint.location} · <strong>Provider:</strong> {complaint.triaged_by}</p>
            <StatusEditor complaint={complaint} onUpdated={() => setRevision((value) => value + 1)} />
          </article>
        ))}
      </div>

      {data && data.total > 0 && <nav className="pagination" aria-label="Pagination"><button type="button" className="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {page} of {totalPages} · {data.total} total</span><button type="button" className="secondary" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</button></nav>}
    </main>
  )
}
