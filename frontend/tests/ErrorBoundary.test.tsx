import { describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { ErrorBoundary } from "../src/ErrorBoundary"

function Boom(): never {
  throw new Error("boom")
}

describe("ErrorBoundary", () => {
  it("shows a fallback instead of a blank page when a view crashes", () => {
    vi.spyOn(console, "error").mockImplementation(() => {})
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    )
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong")
  })
})
