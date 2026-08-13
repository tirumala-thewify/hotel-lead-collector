import { businessKey, displayBusinessValue } from '../businessIdentity.js'

const missingValue = '—'

function display(value) {
  return displayBusinessValue(value, missingValue)
}

// ============================================================
// BUSINESS RESULTS TABLE
// Displays generic business results across every supported category.
// ============================================================
function contactQuality(business) {
  if (business.phone && business.website && business.address) return 'Complete'
  const available = ['phone', 'email', 'website', 'address'].filter((field) => business[field]).length
  if (available >= 2) return 'Good'
  if (available === 1) return 'Partial'
  return 'Minimal'
}

function BusinessTable({ businesses, selectedBusinessKeys, onToggleBusiness, selectedBusiness, onSelectBusiness, onView }) {
  const selectedKey = selectedBusiness
    ? businessKey(selectedBusiness)
    : null
  return (
    <div className="table-card">
      <div className="table-scroll">
        <table className="hotel-results-table">
          <thead><tr>
            <th scope="col" className="selection-cell"><span className="sr-only">Select</span></th>
            <th scope="col">#</th><th scope="col">Business Name</th><th scope="col">Distance</th>
            <th scope="col">Phone</th><th scope="col">Email</th><th scope="col">Contact Status</th><th scope="col">Action</th>
          </tr></thead>
          <tbody>{businesses.map((business, index) => {
            const key = businessKey(business)
            const quality = contactQuality(business)
            return <tr key={key} className={selectedKey === key ? 'selected-hotel-row' : ''} onClick={() => onSelectBusiness(business)}>
              <td className="selection-cell"><input type="checkbox" aria-label={`Select ${business.name}`} checked={selectedBusinessKeys.includes(key)} onClick={(event) => event.stopPropagation()} onChange={() => onToggleBusiness(key)} /></td>
              <td className="serial-cell">{index + 1}</td>
              <td className="hotel-name">{display(business.name)}</td>
              <td>{business.distance_km == null ? missingValue : `${Number(business.distance_km).toFixed(2)} km`}</td>
              <td>{display(business.phone)}</td><td>{display(business.email)}</td>
              <td><span className={`contact-badge contact-${quality.toLowerCase()}`}>{quality}</span></td>
              <td><button type="button" className="view-button" onClick={(event) => { event.stopPropagation(); onSelectBusiness(business); onView(business) }}>View</button></td>
            </tr>
          })}</tbody>
        </table>
      </div>
    </div>
  )
}

export default BusinessTable
