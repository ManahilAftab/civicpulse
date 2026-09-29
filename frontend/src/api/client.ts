export type Complaint = {
  id: string
  text: string
  location: string
  reporter_contact: string | null
  category: string
  priority: string
  status: string
  ai_summary: string | null
  triaged_by: string
  triage_latency_ms: number
  created_at: string
  updated_at: string
}

export type ComplaintInput = {
  text: string
  location: string
  reporter_contact?: string
}

export type ComplaintPage = {
  items: Complaint[]
  total: number
  page: number
  page_size: number
}

export type Stats = {
  total: number
  by_category: Record<string, number>
  by_priority: Record<string, number>
  by_status: Record<string, number>
}

type ErrorBody = {
  detail?: string
  errors?: Array<{ field: string; message: string }>
}

async function readResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>

  let body: ErrorBody = {}
  try {
    body = (await response.json()) as ErrorBody
  } catch {
    // Keep the fallback message when an upstream error is not JSON.
  }

  const validationMessage = body.errors
    ?.map((item) => `${item.field}: ${item.message}`)
    .join("\n")
  let message = validationMessage || body.detail || `Request failed (${response.status})`
  const retryAfter = response.headers.get("Retry-After")
  if (response.status === 429 && retryAfter) {
    message += ` Retry after ${retryAfter} seconds.`
  }
  throw new Error(message)
}

export async function submitComplaint(input: ComplaintInput): Promise<Complaint> {
  const response = await fetch("/api/complaints", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  })
  return readResponse<Complaint>(response)
}

export async function getComplaints(
  params: URLSearchParams,
  signal?: AbortSignal,
): Promise<ComplaintPage> {
  const query = params.toString()
  const response = await fetch(`/api/complaints${query ? `?${query}` : ""}`, { signal })
  return readResponse<ComplaintPage>(response)
}

export async function updateStatus(id: string, status: string): Promise<Complaint> {
  const response = await fetch(`/api/complaints/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  })
  return readResponse<Complaint>(response)
}

export async function getStats(signal?: AbortSignal): Promise<{ data: Stats; cache: string }> {
  const response = await fetch("/api/stats", { signal })
  const data = await readResponse<Stats>(response)
  return { data, cache: response.headers.get("X-Cache") ?? "Not reported" }
}
