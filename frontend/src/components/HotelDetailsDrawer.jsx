import { useEffect } from 'react'

const missing = 'Not Available'
const fields = ['phone', 'email', 'website', 'address', 'brand']

function value(item) {
  return item === null || item === undefined || item === '' ? missing : item
}

function HotelDetailsDrawer({ hotel, onClose, onEnrich, onFindManagers, enriching, findingManagers, managerAvailable }) {
  useEffect(() => {
    if (!hotel) return undefined
    const closeOnEscape = (event) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [hotel, onClose])

  if (!hotel) return null
  const sources = hotel.enrichment_sources || {}
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <aside className="hotel-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header>
          <div>
            <span className="section-kicker">Hotel details</span>
            <h2 id="drawer-title">{value(hotel.name)}</h2>
            <p>{hotel.distance_km == null ? 'Distance unavailable' : `${Number(hotel.distance_km).toFixed(2)} km from selected location`}</p>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close hotel details">×</button>
        </header>

        <section><h3>Contact</h3><dl className="detail-list">
          <div><dt>Phone</dt><dd>{value(hotel.phone)}</dd></div>
          <div><dt>Email</dt><dd>{value(hotel.email)}</dd></div>
          <div><dt>Website</dt><dd>{hotel.website ? <a href={hotel.website} target="_blank" rel="noopener noreferrer">Open website ↗</a> : missing}</dd></div>
          <div className="wide-detail"><dt>Address</dt><dd>{value(hotel.address)}</dd></div>
        </dl></section>

        <section><h3>Hotel</h3><dl className="detail-list">
          <div><dt>Brand</dt><dd>{value(hotel.brand)}</dd></div>
          <div><dt>Stars</dt><dd>{value(hotel.stars)}</dd></div>
          <div><dt>Source</dt><dd>{value(hotel.source)}</dd></div>
          <div><dt>Coordinates</dt><dd>{value(hotel.latitude)}, {value(hotel.longitude)}</dd></div>
        </dl></section>

        <section><h3>Data sources</h3><dl className="source-detail-list">
          {fields.map((field) => <div key={field}><dt>{field}</dt><dd>{value(sources[field] || (hotel[field] ? hotel.source : null))}</dd></div>)}
        </dl></section>

        <section><h3>Managers</h3>
          {hotel.manager_contacts?.length ? hotel.manager_contacts.map((contact, index) => (
            <article className="drawer-manager" key={`${contact.name}-${index}`}>
              <span>{contact.department}</span><strong>{value(contact.name)}</strong><p>{value(contact.title)}</p>
              {contact.email && <a href={`mailto:${contact.email}`}>{contact.email}</a>}
              {contact.linkedin_url && <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">LinkedIn profile ↗</a>}
            </article>
          )) : <p className="muted-copy">No manager contacts loaded.</p>}
        </section>

        <footer className="drawer-actions">
          <button type="button" className="secondary-action" disabled={!hotel.website || enriching} onClick={() => onEnrich(hotel)}>
            {enriching ? 'Enriching...' : 'Enrich Hotel'}
          </button>
          <button type="button" className="primary-action" disabled={!managerAvailable || findingManagers} onClick={() => onFindManagers(hotel)} title={managerAvailable ? 'Search Apollo for hotel decision-makers' : 'Configure and enable Apollo in Settings'}>
            {findingManagers ? 'Finding...' : 'Find Managers'}
          </button>
        </footer>
      </aside>
    </div>
  )
}

export default HotelDetailsDrawer
