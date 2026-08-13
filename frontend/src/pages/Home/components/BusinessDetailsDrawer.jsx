import { useEffect } from 'react'
import { displayBusinessValue } from '../businessIdentity.js'

const missing = 'Not Available'
const fields = ['phone', 'email', 'website', 'address', 'brand']

function value(item) {
  return displayBusinessValue(item, missing)
}

function statusMessage(status) {
  if (status === 'FOUND') return 'Decision-makers found.'
  if (status === 'PARTIAL') return 'Partial decision-maker information found.'
  if (status === 'NOT_FOUND') return 'No matching decision-makers found.'
  if (status === 'ERROR') return 'Unable to retrieve decision-maker information.'
  if (status === 'DISABLED') return 'Apollo is disabled in Settings.'
  return 'No decision-maker search has been run.'
}

// ============================================================
// BUSINESS DETAILS
// Displays enriched contact, social, decision-maker, and WhatsApp data.
// ============================================================
function BusinessDetailsDrawer({ business, categoryName, onClose, onEnrich, onFindManagers, enriching, findingManagers, apolloEnabled, apolloConfigured, enrichmentAvailable }) {
  useEffect(() => {
    if (!business) return undefined
    const closeOnEscape = (event) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [business, onClose])

  if (!business) return null
  const sources = business.enrichment_sources || {}
  const decisionMakers = business.decision_makers || business.manager_contacts || []
  const businessEmails = business.business_emails || []
  const businessPhones = business.business_phones || []
  const whatsappContacts = business.whatsapp_contacts || []
  const socialProfiles = business.social_profiles || {}
  const socialSources = business.social_profile_sources || {}
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
            <h2 id="drawer-title">{value(business.name)}</h2>
            <p>{business.distance_km == null ? 'Distance unavailable' : `${Number(business.distance_km).toFixed(2)} km from selected location`}</p>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close business details">×</button>
        </header>

        <section><h3>Business Contact</h3><dl className="detail-list">
          <div><dt>Phone</dt><dd>{value(business.phone)}</dd></div>
          <div><dt>Email</dt><dd>{value(business.email)}</dd></div>
          <div><dt>Website</dt><dd>{business.website ? <a href={business.website} target="_blank" rel="noopener noreferrer">Open website ↗</a> : missing}</dd></div>
          <div className="wide-detail"><dt>Address</dt><dd>{value(business.address)}</dd></div>
        </dl></section>

        <section><h3>Official Website Contacts</h3>
          {businessEmails.length === 0 && businessPhones.length === 0 && <p className="muted-copy">Not available from the official website</p>}
          {businessEmails.map((contact) => <p key={`${contact.email}-${contact.source_url}`}><a href={`mailto:${contact.email}`}>{contact.email}</a> <small>{contact.type || 'other'} · Source: <a href={contact.source_url} target="_blank" rel="noopener noreferrer">official page</a></small></p>)}
          {businessPhones.map((contact) => <p key={`${contact.normalized}-${contact.source_url}`}>{contact.phone} <small>{contact.type || 'general'} · Source: <a href={contact.source_url} target="_blank" rel="noopener noreferrer">official page</a></small></p>)}
        </section>

        {/* WHATSAPP CONTACT EVIDENCE: explicit public evidence only. */}
        <section><h3>WhatsApp</h3>
          {whatsappContacts.length ? whatsappContacts.map((contact) => <dl className="detail-list" key={contact.normalized}>
            <div><dt>WhatsApp</dt><dd>{contact.number}</dd></div>
            <div><dt>Status</dt><dd>Confirmed from public website</dd></div>
            <div className="wide-detail"><dt>Source</dt><dd><a href={contact.source_url} target="_blank" rel="noopener noreferrer">{contact.source_url}</a></dd></div>
          </dl>) : <p className="muted-copy">Not confirmed from the official website</p>}
        </section>

        {Object.values(socialProfiles).some(Boolean) && <section><h3>Social Profiles</h3><dl className="detail-list">
          {['linkedin', 'facebook', 'instagram'].filter((platform) => socialProfiles[platform]).map((platform) => <div key={platform}><dt>{platform[0].toUpperCase() + platform.slice(1)}</dt><dd><a href={socialProfiles[platform]} target="_blank" rel="noopener noreferrer">Open profile</a>{socialSources[platform] && <small>Linked from <a href={socialSources[platform]} target="_blank" rel="noopener noreferrer">official website</a></small>}</dd></div>)}
        </dl></section>}

        <section><h3>Business Information</h3><dl className="detail-list">
          <div><dt>Brand</dt><dd>{value(business.brand)}</dd></div>
          <div><dt>Category</dt><dd>{value(categoryName)}</dd></div>
          {business.stars && <div><dt>Stars</dt><dd>{value(business.stars)}</dd></div>}
          <div><dt>{business.sources?.length > 1 ? 'Sources' : 'Source'}</dt><dd>{value(business.source)}</dd></div>
          <div><dt>Distance</dt><dd>{business.distance_km == null ? missing : `${Number(business.distance_km).toFixed(2)} km`}</dd></div>
          <div><dt>Coordinates</dt><dd>{value(business.latitude)}, {value(business.longitude)}</dd></div>
        </dl></section>

        <section><h3>Decision Makers</h3>
          {decisionMakers.length ? decisionMakers.map((contact, index) => (
            <article className="drawer-manager decision-maker-card" key={contact.id || `${contact.name}-${contact.title}-${contact.organization_name || contact.company || index}`}>
              <span>{value(contact.role_group || contact.department)}</span>
              <strong>{value(contact.name)}</strong>
              <p>{value(contact.title)}</p>
              <dl className="decision-maker-contact">
                <div><dt>Business Email</dt><dd>{contact.business_email || contact.email ? <><a href={`mailto:${contact.business_email || contact.email}`}>{contact.business_email || contact.email}</a><small>Source: {value(contact.business_email_source || contact.source)}</small></> : missing}</dd></div>
                <div><dt>Work Phone</dt><dd>{value(contact.phone)}{contact.phone && <small>Source: {value(contact.phone_source || contact.source)}</small>}</dd></div>
                <div><dt>LinkedIn</dt><dd>{contact.linkedin_url ? <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer">Open Profile</a> : missing}</dd></div>
                <div><dt>{contact.sources?.length > 1 ? 'Sources' : 'Source'}</dt><dd>{value(contact.sources?.join(' + ') || contact.source)}</dd></div>
                {contact.source_url && <div><dt>Evidence</dt><dd><a href={contact.source_url} target="_blank" rel="noopener noreferrer">Official website page</a>{contact.confidence && <small>Confidence: {contact.confidence}</small>}</dd></div>}
              </dl>
            </article>
          )) : <p className="muted-copy">{statusMessage(business.manager_status)}</p>}
          {decisionMakers.length > 0 && <p className={`decision-maker-status status-${String(business.manager_status || 'FOUND').toLowerCase()}`}>{statusMessage(business.manager_status || 'FOUND')}</p>}
        </section>

        <section><h3>Data Sources</h3><dl className="source-detail-list">
          {fields.map((field) => <div key={field}><dt>{field}</dt><dd>{value(sources[field] || business[`${field}_source`] || (business[field] ? business.source : null))}</dd></div>)}
        </dl></section>

        <footer className="drawer-actions">
          {!enrichmentAvailable && <p className="enrichment-limitation">Business contact enrichment for this category will be added in a later phase.</p>}
          {apolloHelp && <p className="enrichment-limitation">{apolloHelp}</p>}
          <button type="button" className="secondary-action" disabled={!enrichmentAvailable || !business.website || enriching} onClick={() => onEnrich(business)}>
            {enriching ? 'Enriching...' : 'Enrich Business'}
          </button>
          <button type="button" className="primary-action" disabled={!decisionMakerAvailable || findingManagers} onClick={() => onFindManagers(business)} title={decisionMakerAvailable ? 'Search Apollo for business decision-makers' : apolloHelp}>
            {findingManagers ? 'Finding decision-makers...' : 'Find Decision Makers'}
          </button>
        </footer>
      </aside>
    </div>
  )
}

export default BusinessDetailsDrawer
