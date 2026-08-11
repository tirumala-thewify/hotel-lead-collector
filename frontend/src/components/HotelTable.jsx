const missingValue = '—'

function display(value) {
  return value === null || value === undefined || value === '' ? missingValue : value
}

function contactQuality(hotel) {
  if (hotel.phone && hotel.website && hotel.address) return 'Complete'
  const available = ['phone', 'email', 'website', 'address'].filter((field) => hotel[field]).length
  if (available >= 2) return 'Good'
  if (available === 1) return 'Partial'
  return 'Minimal'
}

function HotelTable({ hotels, selectedHotelKeys, onToggleHotel, selectedHotel, onSelectHotel, onView }) {
  const selectedKey = selectedHotel
    ? selectedHotel.id || selectedHotel.place_id || `${selectedHotel.osm_type}-${selectedHotel.osm_id}`
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
          <tbody>{hotels.map((hotel, index) => {
            const key = hotel.id || hotel.place_id || `${hotel.osm_type}-${hotel.osm_id}`
            const quality = contactQuality(hotel)
            return <tr key={key} className={selectedKey === key ? 'selected-hotel-row' : ''} onClick={() => onSelectHotel(hotel)}>
              <td className="selection-cell"><input type="checkbox" aria-label={`Select ${hotel.name}`} checked={selectedHotelKeys.includes(key)} onClick={(event) => event.stopPropagation()} onChange={() => onToggleHotel(key)} /></td>
              <td className="serial-cell">{index + 1}</td>
              <td className="hotel-name">{display(hotel.name)}</td>
              <td>{hotel.distance_km == null ? missingValue : `${Number(hotel.distance_km).toFixed(2)} km`}</td>
              <td>{display(hotel.phone)}</td><td>{display(hotel.email)}</td>
              <td><span className={`contact-badge contact-${quality.toLowerCase()}`}>{quality}</span></td>
              <td><button type="button" className="view-button" onClick={(event) => { event.stopPropagation(); onSelectHotel(hotel); onView(hotel) }}>View</button></td>
            </tr>
          })}</tbody>
        </table>
      </div>
    </div>
  )
}

export default HotelTable
