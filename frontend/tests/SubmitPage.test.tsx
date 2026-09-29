import { describe, expect, it } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { SubmitPage } from "../src/SubmitPage"
import { complaint, jsonResponse, stubFetch } from "./helpers"

function fill(text: string, location: string) {
  fireEvent.change(screen.getByLabelText("What happened?"), { target: { value: text } })
  fireEvent.change(screen.getByLabelText("Location"), { target: { value: location } })
  fireEvent.submit(screen.getByRole("button", { name: "Submit complaint" }).closest("form")!)
}

describe("SubmitPage", () => {
  it("blocks a too-short complaint client-side without calling the API", () => {
    const fetchMock = stubFetch()
    render(<SubmitPage />)
    fill("short", "G-9/2")
    expect(screen.getByRole("alert")).toHaveTextContent("10 to 2000 characters")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("renders category, priority, AI summary and the provider that triaged it", async () => {
    stubFetch(jsonResponse(complaint, 201))
    render(<SubmitPage />)
    fill(complaint.text, complaint.location)
    expect(await screen.findByText("Complaint submitted")).toBeInTheDocument()
    expect(screen.getByText("water")).toBeInTheDocument()
    expect(screen.getByText("high")).toBeInTheDocument()
    expect(screen.getByText(complaint.ai_summary)).toBeInTheDocument()
    expect(screen.getByText("llm:groq")).toBeInTheDocument()
  })

  it("shows an honest loading state while triage is in progress", async () => {
    let resolve!: (r: Response) => void
    const pending = new Promise<Response>((r) => (resolve = r))
    stubFetch()
    ;(globalThis.fetch as unknown as { mockReturnValueOnce: (p: Promise<Response>) => void })
      .mockReturnValueOnce(pending)
    render(<SubmitPage />)
    fill(complaint.text, complaint.location)
    expect(await screen.findByText("The report is being triaged…")).toBeInTheDocument()
    resolve(jsonResponse(complaint, 201))
    expect(await screen.findByText("Complaint submitted")).toBeInTheDocument()
  })

  it("shows the server's field-level validation errors", async () => {
    stubFetch(
      jsonResponse(
        { detail: "Validation failed", errors: [{ field: "location", message: "too short" }] },
        400,
      ),
    )
    render(<SubmitPage />)
    fill(complaint.text, complaint.location)
    expect(await screen.findByRole("alert")).toHaveTextContent("location: too short")
  })
})
