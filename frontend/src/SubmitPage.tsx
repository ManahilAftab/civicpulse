import { useState, type FormEvent } from "react"
import { submitComplaint, type Complaint } from "./api/client"

export function SubmitPage() {
  const [text, setText] = useState("")
  const [location, setLocation] = useState("")
  const [contact, setContact] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [result, setResult] = useState<Complaint | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    setResult(null)
    const cleanText = text.trim()
    const cleanLocation = location.trim()
    const cleanContact = contact.trim()

    if (cleanText.length < 10 || cleanText.length > 2000) {
      setError("Complaint text must contain 10 to 2000 characters.")
      return
    }
    if (cleanLocation.length < 3 || cleanLocation.length > 200) {
      setError("Location must contain 3 to 200 characters.")
      return
    }
    if (cleanContact.length > 200) {
      setError("Reporter contact must be at most 200 characters.")
      return
    }

    setLoading(true)
    try {
      const complaint = await submitComplaint({
        text: cleanText,
        location: cleanLocation,
        ...(cleanContact ? { reporter_contact: cleanContact } : {}),
      })
      setResult(complaint)
      setText("")
      setLocation("")
      setContact("")
    } catch (caught) {
      setError(caught instanceof TypeError ? "Cannot reach the CivicPulse API." : (caught as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page two-column">
      <section className="intro">
        <p className="eyebrow">Community reporting</p>
        <h1>Report an issue in your area</h1>
        <p>Tell the civic team what happened and where. CivicPulse will triage the report and assign a priority.</p>
      </section>

      <section className="card">
        <h2>New complaint</h2>
        <form onSubmit={submit}>
          <fieldset disabled={loading}>
            <label htmlFor="complaint-text">What happened?</label>
            <textarea id="complaint-text" minLength={10} maxLength={2000} value={text} onChange={(event) => setText(event.target.value)} required />
            <small>{text.length}/2000 characters</small>

            <label htmlFor="location">Location</label>
            <input id="location" minLength={3} maxLength={200} value={location} onChange={(event) => setLocation(event.target.value)} required />

            <label htmlFor="contact">Contact (optional)</label>
            <input id="contact" maxLength={200} value={contact} onChange={(event) => setContact(event.target.value)} />

            <button type="submit">{loading ? "Submitting…" : "Submit complaint"}</button>
          </fieldset>
        </form>
        {loading && <p role="status">The report is being triaged…</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {result && (
          <div className="success" role="status">
            <h3>Complaint submitted</h3>
            <dl>
              <div><dt>Category</dt><dd>{result.category}</dd></div>
              <div><dt>Priority</dt><dd>{result.priority}</dd></div>
              <div><dt>Summary</dt><dd>{result.ai_summary || "No summary"}</dd></div>
              <div><dt>Triaged by</dt><dd>{result.triaged_by}</dd></div>
            </dl>
          </div>
        )}
      </section>
    </main>
  )
}
