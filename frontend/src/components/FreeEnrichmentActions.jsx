import { useState } from 'react'

function FreeEnrichmentActions({ selectedHotels, running, summary, error, onRun }) {
  const [confirming, setConfirming] = useState(false)
  const count = selectedHotels.length
  const tooMany = count > 10
  return (
    <>
      <div className="toolbar-action">
        <button
          type="button"
          className="free-enrich-button"
          disabled={!count || tooMany || running}
          onClick={() => setConfirming(true)}
        >
          {running ? 'Enriching...' : 'Enrich Selected'}
        </button>
        {(tooMany || error) && <span className="action-note">{tooMany ? 'Maximum 10 hotels' : error}</span>}
      </div>
      {summary && (
        <div className="free-enrichment-summary" role="status">
          <strong>FREE ENRICHMENT RESULT</strong>
          <span>Hotels processed: {summary.processed}</span>
          <span>Hotels improved: {summary.improved}</span>
          {Object.entries(summary.fields_added).map(([field, total]) => (
            <span key={field}>{field[0].toUpperCase() + field.slice(1)}: +{total}</span>
          ))}
        </div>
      )}
      {confirming && (
        <div className="confirmation-backdrop" role="presentation">
          <section className="confirmation-dialog" role="dialog" aria-modal="true" aria-labelledby="free-confirm-title">
            <h2 id="free-confirm-title">Confirm free enrichment</h2>
            <p>Enrich {count} selected {count === 1 ? 'hotel' : 'hotels'} using public hotel websites?</p>
            <p>This may take a little time because websites are checked sequentially.</p>
            <div className="confirmation-actions">
              <button type="button" onClick={() => setConfirming(false)}>Cancel</button>
              <button type="button" className="free-enrich-button" onClick={() => { setConfirming(false); onRun() }}>Continue</button>
            </div>
          </section>
        </div>
      )}
    </>
  )
}

export default FreeEnrichmentActions
