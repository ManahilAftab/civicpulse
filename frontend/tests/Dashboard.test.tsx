import { describe, expect, it } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { Dashboard } from "../src/Dashboard"
import { complaint, jsonResponse, stubFetch } from "./helpers"

const page = { items: [{ ...complaint, status: "resolved" }], total: 1, page: 1, page_size: 10 }

describe("Dashboard", () => {
  it("surfaces the server's 409 message verbatim on an invalid transition", async () => {
    stubFetch(
      jsonResponse(page),
      jsonResponse({ detail: "Invalid status transition: resolved -> open" }, 409),
    )
    render(<Dashboard />)
    const select = await screen.findByLabelText("New status")
    fireEvent.change(select, { target: { value: "open" } })
    fireEvent.click(screen.getByRole("button", { name: "Update" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid status transition: resolved -> open",
    )
  })

  it("sends the chosen filter to the API and resets to page 1", async () => {
    const fetchMock = stubFetch(jsonResponse(page), jsonResponse(page))
    render(<Dashboard />)
    await screen.findByText(complaint.text)
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "water" } })
    await screen.findByText(complaint.text)
    const url = String(fetchMock.mock.calls.at(-1)?.[0])
    expect(url).toContain("category=water")
    expect(url).toContain("page=1")
  })
})
