import { useEffect } from 'react'

const missing = 'Not Available'
const fields = ['phone', 'email', 'website', 'address', 'brand']

function value(item) {
  return item === null || item === undefined || item === '' ? missing : item
}

function statusMessage(status) {
  if (status === 'FOUND') return 'Decision-makers found.'
  if (status === 'PARTIAL') return 'Partial decision-maker information found.'
  if (status === 'NOT_FOUND') return 'No matching decision-makers found.'
  if (status === 'ERROR') return 'Unable to retrieve decision-maker information.'
  if (status === 'DISABLED') return 'Apollo is disabled in Settings.'
  return 'No decision-maker search has been run.'
}

function HotelDetailsDrawer({ hotel, categoryName, onClose, onEnrich, onFindManagers, enriching, findingManagers, apolloEnabled, apolloConfigured, enrichmentAvailable }) {
  useEffect(() => {
    if (!hotel) return undefined
    const closeOnEscape = (event) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [hotel, onClose])

  if (!hotel) return null
  const sources = hotel.enrichment_sources || {}
  const decisionMakers = (hotel.decision_makers || hotel.manager_contacts || []).slice(0, 3)
  const decisionMakerAvailable = apolloEnabled && apolloConfigured
  const apolloHelp = !apolloEnabled
    ? 'Apollo is disabled in Settings.'
    : !apolloConfigured ? 'Apollo API key is not configured.' : ''
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <aside className="hotel-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header>
          <div>
            <span className="section-kicker">Business details</span>
            <h2 id="drawer-title">{value(hotel.name)}</h2>
            <p>{hotel.distance_km == null ? 'Distance unavailable' : `${Number(hotel.distance_km).toFixed(2)} km from selected location`}</p>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close business details">×</button>
        </header>

        <section><h3>Business Contact</h3><dl className="detail-list">
          <div><dt>Phone</dt><dd>{value(hotel.phone)}</dd></div>
          <div><dt>Email</dt><dd>{value(hotel.email)}</dd></div>
          <div><dt>Website</dt><dd>{hotel.website ? <a href={hotel.website} target="_blank" rel="noopener noreferrer">Open website ↗</a> : missing}</dd></div>
          <div className="wide-detail"><dt>Address</dt><dd>{value(hotel.address)}</dd></div>
        </dl></section>

        <section><h3>Business Information</h3><dl className="detail-list">
          <div><dt>Brand</dt><dd>{value(hotel.brand)}</dd></div>
          <div><dt>Category</dt><dd>{value(categoryName)}</dd></div>
          {hotel.stars && <div><dt>Stars</dt><dd>{value(hotel.stars)}</dd></div>}
          <div><dt>Source</dt><dd>{value(hotel.source)}</dd></div>
          <div><dt>Distance</dt><dd>{hotel.distance_km == null ? missing : `${Number(hotel.distance_km).toFixed(2)} km`}</dd></div>
          <div><dt>Coordinates</dt><dd>{value(hotel.latitude)}, {value(hotel.longitude)}</dd></div>
        </dl></section>

        <section><h3>Decision Makers</h3>
          {decisionMakers.length ? decisionMakers.map((contact, index) => (
            <article className="drawer-manager decision-maker-card" key={contact.id || `${contact.name}-${contact.title}-${contact.organization_name || contact.company || index}`}>
              <span>{value(contact.role_group || contact.department)}</span>
              <strong>{value(contact.name)}</strong>
              <p>{value(contact.title)}</p>
              <dl className="decision-maker-contact">
                <div><dt>Business Email</dt><dd>{contact.business_email || contact.email ? <a href={`mailto:${contact.business_email || contact.email}`}>{contact.business_email || contact.email}</a> : missing}</dd></div>
                <div><dt>Work Phone</dt><dd>{value(contact.phone)}</dd></div>
                <div><dt>LinkedIn</dt><dd>{contact.linkedin_url ? <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">Open Profile</a> : missing}</dd></div>
                <div><dt>Source</dt><dd>{value(contact.source)}</dd></div>
              </dl>
            </article>
          )) : <p className="muted-copy">{statusMessage(hotel.manager_status)}</p>}
          {decisionMakers.length > 0 && <p className={`decision-maker-status status-${String(hotel.manager_status || 'FOUND').toLowerCase()}`}>{statusMessage(hotel.manager_status || 'FOUND')}</p>}
        </section>

        <section><h3>Data Sources</h3><dl className="source-detail-list">
          {fields.map((field) => <div key={field}><dt>{field}</dt><dd>{value(sources[field] || (hotel[field] ? hotel.source : null))}</dd></div>)}
        </dl></section>

        <footer className="drawer-actions">
          {!enrichmentAvailable && <p className="enrichment-limitation">Business contact enrichment for this category will be added in a later phase.</p>}
          {apolloHelp && <p className="enrichment-limitation">{apolloHelp}</p>}
          <button type="button" className="secondary-action" disabled={!enrichmentAvailable || !hotel.website || enriching} onClick={() => onEnrich(hotel)}>
            {enriching ? 'Enriching...' : 'Enrich Business'}
          </button>
          <button type="button" className="primary-action" disabled={!decisionMakerAvailable || findingManagers} onClick={() => onFindManagers(hotel)} title={decisionMakerAvailable ? 'Search Apollo for business decision-makers' : apolloHelp}>
            {findingManagers ? 'Finding decision-makers...' : 'Find Decision Makers'}
          </button>
        </footer>
      </aside>
    </div>
  )
}

export default HotelDetailsDrawer
