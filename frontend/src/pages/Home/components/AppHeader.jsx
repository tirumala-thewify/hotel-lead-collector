function AppHeader({ providerName }) {
  return (
    <header className="app-header">
      <div>
        <h1>Business Lead Collector</h1>
        <p>Find businesses and decision-makers near any location.</p>
      </div>
      <nav className="header-actions" aria-label="Application navigation">
        <span className="provider-indicator">{providerName}</span>
        <a href="/settings">Settings</a>
      </nav>
    </header>
  )
}

export default AppHeader
