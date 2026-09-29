import { Component, type ErrorInfo, type ReactNode } from "react"

type Props = { children: ReactNode }
type State = { hasError: boolean }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Frontend error", error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="page narrow">
          <section className="card error-card" role="alert">
            <h1>Something went wrong</h1>
            <p>Reload the page and try again.</p>
            <button onClick={() => window.location.reload()}>Reload</button>
          </section>
        </main>
      )
    }
    return this.props.children
  }
}
