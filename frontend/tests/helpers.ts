import { vi } from "vitest"

export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  })
}

export function stubFetch(...responses: Response[]) {
  const fetchMock = vi.fn()
  for (const r of responses) fetchMock.mockResolvedValueOnce(r)
  vi.stubGlobal("fetch", fetchMock)
  return fetchMock
}

export const complaint = {
  id: "11111111-1111-4111-8111-111111111111",
  text: "Burst water main flooding Street 12 since fajr",
  location: "G-9/2, Islamabad",
  reporter_contact: null,
  category: "water",
  priority: "high",
  status: "open",
  ai_summary: "Burst main flooding homes on Street 12",
  triaged_by: "llm:groq",
  triage_latency_ms: 812,
  created_at: "2026-09-29T10:00:00Z",
  updated_at: "2026-09-29T10:00:00Z",
}
