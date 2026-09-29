import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { StatsPage } from "../src/StatsPage"
import { jsonResponse, stubFetch } from "./helpers"

const stats = {
  total: 34,
  by_category: { water: 6, electricity: 7, sanitation: 6, roads: 6, streetlights: 4, other: 5 },
  by_priority: { high: 12, normal: 17, low: 5 },
  by_status: { open: 21, in_progress: 7, resolved: 3, rejected: 3 },
}

describe("StatsPage", () => {
  it("renders aggregates and the cache state from the X-Cache header", async () => {
    stubFetch(jsonResponse(stats, 200, { "X-Cache": "HIT" }))
    render(<StatsPage />)
    expect(await screen.findByText("34")).toBeInTheDocument()
    expect(screen.getByText("Cache: HIT")).toBeInTheDocument()
    expect(screen.getByText("By category")).toBeInTheDocument()
  })
})
