import { useState } from 'react'

const MAX_BULK_BUSINESSES = 10

function BulkManagerActions({ selectedHotels, providerSettings, running, summary, error, onRun }) {
  const [confirming, setConfirming] = useState(false)
  const count = selectedHotels.length
  const tooMany = count > MAX_BULK_BUSINESSES
  const apolloEnabled = Boolean(providerSettings?.apollo_enabled)
  const apolloConfigured = Boolean(providerSettings?.apollo_configured)
  const canRun = count > 0 && !tooMany && apolloEnabled && apolloConfigured && !running

  return (
    <>
      <div className="toolbar-action">
          <button type="button" className="bulk-manager-button" disabled={!canRun} onClick={() => setConfirming(true)}>
            {running ? 'Finding decision-makers...' : 'Find Decision Makers'}
          </button>
          <span className="action-note">{tooMany
            ? 'Maximum 10 businesses'
            : !apolloEnabled
              ? 'Apollo is disabled in Settings.'
              : !apolloConfigured
                ? 'Apollo API key is not configured.'
                : error}</span>
      </div>
      {summary && (
        <div className="bulk-summary" role="status">
          <strong>Processed: {summary.processed}</strong>
          <span>Found: {summary.found}</span>
          <span>Not found: {summary.not_found}</span>
          <span>Errors: {summary.errors}</span>
        </div>
      )}
      {confirming && (
        <div className="confirmation-backdrop" role="presentation">
          <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="bulk-confirm-title">
            <h2 id="bulk-confirm-title">Find Decision Makers</h2>
            <p>Find decision-makers for {count} selected {count === 1 ? 'business' : 'businesses'}?</p>
            <p>Some Apollo enrichment requests may consume credits.</p>
            <div className="confirmation-actions">
              <button type="button" onClick={() => setConfirming(false)}>Cancel</button>
              <button type="button" className="bulk-manager-button" onClick={() => { setConfirming(false); onRun() }}>
                Continue
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  )
}

export default BulkManagerActions
