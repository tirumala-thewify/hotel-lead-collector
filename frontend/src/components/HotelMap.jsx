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

const searchIcon = L.divIcon({
  className: 'search-map-marker',
  html: '<span></span>',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
})
const hotelIcon = L.divIcon({
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

function MapController({ center, selectedHotel, markerRefs }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, map.getZoom(), { animate: true })
  }, [center, map])
  useEffect(() => {
    if (!selectedHotel?.latitude || !selectedHotel?.longitude) return
    map.setView([selectedHotel.latitude, selectedHotel.longitude], Math.max(map.getZoom(), 15), {
      animate: true,
    })
    markerRefs.current.get(selectedHotel.id)?.openPopup()
  }, [map, markerRefs, selectedHotel])
  return null
}

function available(value) {
  return value || 'Not Available'
}

function HotelMap({ location, radius, hotels, onLocationChange, selectedHotel, onSelectHotel }) {
  const markerRefs = useRef(new Map())
  const center = useMemo(() => [Number(location.latitude), Number(location.longitude)], [location])
  const mapHotels = hotels.filter((hotel) => (
    Number.isFinite(Number(hotel.latitude)) && Number.isFinite(Number(hotel.longitude))
  )).slice(0, 100)

  return (
    <section className="map-card" aria-label="Hotel location map">
      <MapContainer center={center} zoom={12} scrollWheelZoom className="hotel-map">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <MapClickHandler onLocationChange={onLocationChange} />
        <MapController center={center} selectedHotel={selectedHotel} markerRefs={markerRefs} />
        <Circle center={center} radius={Number(radius)} pathOptions={{ color: '#246bfd', fillOpacity: 0.09 }} />
        <Marker position={center} icon={searchIcon}>
          <Popup>
            <strong>Search Location</strong><br />
            Lat: {Number(location.latitude).toFixed(5)}<br />
            Lng: {Number(location.longitude).toFixed(5)}<br />
            Radius: {(Number(radius) / 1000).toFixed(0)} km
          </Popup>
        </Marker>
        {mapHotels.map((hotel) => (
          <Marker
            key={hotel.id || hotel.place_id}
            position={[hotel.latitude, hotel.longitude]}
            icon={hotelIcon}
            ref={(marker) => {
              const key = hotel.id || hotel.place_id
              if (marker) markerRefs.current.set(key, marker)
              else markerRefs.current.delete(key)
            }}
            eventHandlers={{ click: () => onSelectHotel(hotel) }}
          >
            <Popup>
              <strong>{available(hotel.name)}</strong><br />
              {hotel.distance_km == null ? 'Distance: Not Available' : `${Number(hotel.distance_km).toFixed(2)} km`}<br />
              Phone: {available(hotel.phone)}<br />
              Email: {available(hotel.email)}<br />
              Website: {hotel.website ? <a href={hotel.website} target="_blank" rel="noopener noreferrer">Open Website</a> : 'Not Available'}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
      <p className="map-help">Search above or click anywhere on the map to choose a location. Hotel search runs only when you click Find Hotels.</p>
    </section>
  )
}

export default HotelMap
