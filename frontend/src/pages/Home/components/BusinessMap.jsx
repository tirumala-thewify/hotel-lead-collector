import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import {
  Circle,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import { businessCoordinates, mappableBusinesses } from './mapCoordinates.js'
import { businessKey } from '../businessIdentity.js'

const searchIcon = L.divIcon({
  className: 'search-map-marker',
  html: '<span></span>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
})
const businessIcon = L.divIcon({
  className: 'hotel-map-marker',
  html: '<span></span>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})

function MapClickHandler({ onLocationChange }) {
  useMapEvents({
    click(event) {
      onLocationChange({ latitude: event.latlng.lat, longitude: event.latlng.lng })
    },
  })
  return null
}

function MapController({ center, selectedBusiness, markerRefs }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true })
  }, [center, map])
  useEffect(() => {
    const coordinates = businessCoordinates(selectedBusiness)
    if (!coordinates) return
    map.setView(coordinates, Math.max(map.getZoom(), 15), {
      animate: true,
    })
    markerRefs.current.get(businessKey(selectedBusiness))?.openPopup()
  }, [map, markerRefs, selectedBusiness])
  return null
}

function available(value) {
  return value || 'Not Available'
}

// ============================================================
// BUSINESS MAP
// Displays generic business markers regardless of selected category.
// ============================================================
function BusinessMap({ location, radius, businesses, onLocationChange, selectedBusiness, onSelectBusiness }) {
  const markerRefs = useRef(new Map())
  const center = useMemo(() => [Number(location.latitude), Number(location.longitude)], [location])
  const mappedBusinesses = mappableBusinesses(businesses)

  return (
    <section className="map-card" aria-label="Business location map">
      <MapContainer center={center} zoom={12} scrollWheelZoom className="hotel-map">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <MapClickHandler onLocationChange={onLocationChange} />
        <MapController center={center} selectedBusiness={selectedBusiness} markerRefs={markerRefs} />
        <Circle center={center} radius={Number(radius)} pathOptions={{ color: '#246bfd', fillOpacity: 0.09 }} />
        <Marker position={center} icon={searchIcon}>
          <Popup>
            <strong>Search Location</strong><br />
            Lat: {Number(location.latitude).toFixed(5)}<br />
            Lng: {Number(location.longitude).toFixed(5)}<br />
            Radius: {(Number(radius) / 1000).toFixed(0)} km
          </Popup>
        </Marker>
        {mappedBusinesses.map(({ business, coordinates }) => (
          <Marker
            key={businessKey(business)}
            position={coordinates}
            icon={businessIcon}
            ref={(marker) => {
              const key = businessKey(business)
              if (marker) markerRefs.current.set(key, marker)
              else markerRefs.current.delete(key)
            }}
            eventHandlers={{ click: () => onSelectBusiness(business) }}
          >
            <Popup>
              <strong>{available(business.name)}</strong><br />
              {business.distance_km == null ? 'Distance: Not Available' : `${Number(business.distance_km).toFixed(2)} km`}<br />
              Phone: {available(business.phone)}<br />
              Email: {available(business.email)}<br />
              Website: {business.website ? <a href={business.website} target="_blank" rel="noopener noreferrer">Open Website</a> : 'Not Available'}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <p className="map-help">Search above or click anywhere on the map to choose a location. Business search runs only when you click Find Businesses.</p>
    </section>
  )
}

export default BusinessMap
