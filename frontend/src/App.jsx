import { useEffect, useState } from 'react'
import HotelTable from './components/HotelTable.jsx'
import HotelMap from './components/HotelMap.jsx'
import ExportButtons from './components/ExportButtons.jsx'
import BulkManagerActions from './components/BulkManagerActions.jsx'
import FreeEnrichmentActions from './components/FreeEnrichmentActions.jsx'
import AppHeader from './components/AppHeader.jsx'
import SearchPanel from './components/SearchPanel.jsx'
import SearchSummary from './components/SearchSummary.jsx'
import ResultsToolbar from './components/ResultsToolbar.jsx'
import HotelDetailsDrawer from './components/HotelDetailsDrawer.jsx'
import {
  enrichHotel,
  fetchNearbyHotels,
  findHotelManagers,
  findManagersBulk,
  freeEnrichHotelsBulk,
  HotelServiceError,
} from './services/hotelService.js'
import './index.css'
import { fetchProviderSettings } from './services/providerSettingsService.js'

function App() {
  const [hotels, setHotels] = useState([])
  const [hasSearched, setHasSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [enrichingHotels, setEnrichingHotels] = useState({})
  const [managerSearches, setManagerSearches] = useState({})
  const [providerSettings, setProviderSettings] = useState(null)
  const [selectedHotelKeys, setSelectedHotelKeys] = useState([])
  const [bulkManagerRunning, setBulkManagerRunning] = useState(false)
  const [bulkManagerSummary, setBulkManagerSummary] = useState(null)
  const [bulkManagerError, setBulkManagerError] = useState('')
  const [freeEnrichmentRunning, setFreeEnrichmentRunning] = useState(false)
  const [freeEnrichmentSummary, setFreeEnrichmentSummary] = useState(null)
  const [freeEnrichmentError, setFreeEnrichmentError] = useState('')
  const [searchValues, setSearchValues] = useState({
    lat: '28.5562',
    lng: '77.1000',
    radius: '5000',
  })
  const [selectedHotel, setSelectedHotel] = useState(null)
  const [drawerHotelKey, setDrawerHotelKey] = useState(null)
  const [selectedLocationName, setSelectedLocationName] = useState('Delhi Airport')

  useEffect(() => {
    fetchProviderSettings().then(setProviderSettings).catch(() => {})
  }, [])

  const handleSearch = async ({ lat, lng, radius }) => {
    if (loading) return

    setLoading(true)
    setError('')
    setHasSearched(false)

    try {
      const data = await fetchNearbyHotels(lat, lng, radius)
      setHotels(data.hotels)
      setSelectedHotelKeys([])
      setBulkManagerSummary(null)
      setFreeEnrichmentSummary(null)
      setSelectedHotel(null)
      setDrawerHotelKey(null)
      setHasSearched(true)
    } catch (requestError) {
      setHotels([])
      if (requestError instanceof HotelServiceError && requestError.status === 502) {
        setError('Hotel data service is temporarily unavailable. Please try again later.')
      } else {
        setError(requestError.message || 'Unable to search for hotels. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleLocationChange = ({ latitude, longitude }) => {
    setSearchValues((current) => ({
      ...current,
      lat: Number(latitude).toFixed(6),
      lng: Number(longitude).toFixed(6),
    }))
    setSelectedHotel(null)
    setSelectedLocationName('Selected map location')
  }

  const handleLocationSelect = (location) => {
    setSelectedLocationName(location.name || location.display_name || 'Selected location')
    setSearchValues((current) => ({
      ...current,
      lat: Number(location.latitude).toFixed(6),
      lng: Number(location.longitude).toFixed(6),
    }))
    setSelectedHotel(null)
  }

  const handleSearchValuesChange = (values) => {
    if (values.lat !== searchValues.lat || values.lng !== searchValues.lng) {
      setSelectedLocationName('Custom coordinates')
    }
    setSearchValues(values)
  }

  const handleFindManagers = async (hotel) => {
    const key = hotel.id || hotel.place_id || `${hotel.osm_type}-${hotel.osm_id}`
    if (managerSearches[key]) return
    setManagerSearches((current) => ({ ...current, [key]: true }))
    try {
      const result = await findHotelManagers(hotel)
      setHotels((current) => current.map((item) => (
        (item.id || item.place_id || `${item.osm_type}-${item.osm_id}`) === key
          ? {
              ...item,
              manager_contacts: result.contacts,
              manager_status: result.status,
              manager_message: result.contacts.length
                ? ''
                : 'No matching decision-makers were found.',
            }
          : item
      )))
    } catch (managerError) {
      setHotels((current) => current.map((item) => (
        (item.id || item.place_id || `${item.osm_type}-${item.osm_id}`) === key
          ? { ...item, manager_contacts: [], manager_status: 'ERROR', manager_message: managerError.message }
          : item
      )))
    } finally {
      setManagerSearches((current) => ({ ...current, [key]: false }))
    }
  }

  const hotelKey = (hotel) => hotel.id || hotel.place_id || `${hotel.osm_type}-${hotel.osm_id}`
  const selectedHotels = hotels.filter((hotel) => selectedHotelKeys.includes(hotelKey(hotel)))
  const drawerHotel = hotels.find((hotel) => hotelKey(hotel) === drawerHotelKey) || null

  const handleToggleHotel = (key) => {
    setSelectedHotelKeys((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key])
  }

  const handleSelectAll = (checked) => {
    setSelectedHotelKeys(checked ? hotels.map(hotelKey) : [])
  }

  const handleBulkManagers = async () => {
    if (!selectedHotels.length || selectedHotels.length > 10 || bulkManagerRunning) return
    setBulkManagerRunning(true)
    setBulkManagerError('')
    setBulkManagerSummary(null)
    try {
      const data = await findManagersBulk(selectedHotels)
      const resultsByName = new Map(data.results.map((result) => [result.hotel_name, result]))
      setHotels((current) => current.map((hotel) => {
        const result = resultsByName.get(hotel.name)
        if (!result || !selectedHotelKeys.includes(hotelKey(hotel))) return hotel
        return {
          ...hotel,
          manager_contacts: result.contacts,
          manager_status: result.status,
          manager_message: result.status === 'ERROR'
            ? 'Manager search failed for this hotel.'
            : result.contacts.length ? '' : 'No matching decision-makers were found.',
        }
      }))
      setBulkManagerSummary(data.summary)
    } catch (bulkError) {
      setBulkManagerError(bulkError.message)
    } finally {
      setBulkManagerRunning(false)
    }
  }

  const handleBulkFreeEnrichment = async () => {
    if (!selectedHotels.length || selectedHotels.length > 10 || freeEnrichmentRunning) return
    setFreeEnrichmentRunning(true)
    setFreeEnrichmentError('')
    setFreeEnrichmentSummary(null)
    try {
      const data = await freeEnrichHotelsBulk(selectedHotels)
      const resultsByName = new Map(data.results.map((result) => [result.hotel_name, result]))
      setHotels((current) => current.map((hotel) => {
        const result = resultsByName.get(hotel.name)
        if (!result || !selectedHotelKeys.includes(hotelKey(hotel))) return hotel
        return {
          ...hotel,
          ...result.hotel,
          enrichment_status: result.status,
          enrichment_message: result.status === 'ERROR' ? 'Free enrichment failed for this hotel.' : '',
          enrichment_sources: result.sources,
          website_confidence: result.website_confidence,
        }
      }))
      setFreeEnrichmentSummary(data.summary)
    } catch (freeError) {
      setFreeEnrichmentError(freeError.message)
    } finally {
      setFreeEnrichmentRunning(false)
    }
  }

  const handleEnrich = async (hotel) => {
    const key = hotel.id || hotel.place_id || `${hotel.osm_type}-${hotel.osm_id}`
    if (enrichingHotels[key]) return
    setEnrichingHotels((current) => ({ ...current, [key]: true }))

    try {
      const enriched = await enrichHotel(hotel)
      setHotels((current) => current.map((item) => {
        if ((item.id || item.place_id || `${item.osm_type}-${item.osm_id}`) !== key) return item
        return {
          ...item,
          phone: enriched.phone || item.phone,
          email: enriched.email || item.email,
          address: enriched.address || item.address,
          website: enriched.website || item.website,
          enrichment_status: enriched.status,
          enrichment_message: enriched.message || '',
          enrichment_sources: enriched.sources || {},
        }
      }))
    } catch (enrichmentError) {
      setHotels((current) => current.map((item) => (
        (item.id || item.place_id || `${item.osm_type}-${item.osm_id}`) === key
          ? { ...item, enrichment_status: 'ERROR', enrichment_message: enrichmentError.message }
          : item
      )))
    } finally {
      setEnrichingHotels((current) => ({ ...current, [key]: false }))
    }
  }

  return (
    <main className="app-shell">
      <AppHeader providerName={providerSettings?.hotel_provider === 'google' ? 'Google Places' : 'OpenStreetMap'} />
      <SearchPanel onLocationSelect={handleLocationSelect} values={searchValues} onValuesChange={handleSearchValuesChange} onSearch={handleSearch} loading={loading} selectedLocationName={selectedLocationName} />
      <div className="map-summary-workspace">
        <HotelMap location={{ latitude: searchValues.lat, longitude: searchValues.lng }} radius={searchValues.radius} hotels={hotels} onLocationChange={handleLocationChange} selectedHotel={selectedHotel} onSelectHotel={setSelectedHotel} />
        <SearchSummary locationName={selectedLocationName} radius={searchValues.radius} providerName={providerSettings?.hotel_provider === 'google' ? 'Google Places' : 'OpenStreetMap'} hotels={hotels} hasSearched={hasSearched} />
      </div>

      <section className="results-section" aria-live="polite" aria-busy={loading}>
        {loading && <div className="compact-alert loading-status">Searching nearby hotels...</div>}

        {!loading && error && (
          <div className="compact-alert error-status" role="alert">
            <strong>Hotel search temporarily unavailable.</strong>
            <span>The public hotel data service could not respond. Please try again later.</span>
          </div>
        )}

        {!loading && !error && !hasSearched && <div className="clean-empty-state">Search a location and choose a radius to discover nearby hotels.</div>}

        {!loading && !error && hasSearched && hotels.length === 0 && (
          <div className="clean-empty-state">
            <strong>No hotels found in this area.</strong>
            <span>Try increasing the radius or choosing another location.</span>
          </div>
        )}

        {!loading && !error && hasSearched && hotels.length > 0 && (
          <>
            <ResultsToolbar count={hotels.length} selectedCount={selectedHotels.length} allSelected={selectedHotels.length === hotels.length} onSelectAll={handleSelectAll} onClear={() => setSelectedHotelKeys([])}>
            <FreeEnrichmentActions
              selectedHotels={selectedHotels}
              running={freeEnrichmentRunning}
              summary={freeEnrichmentSummary}
              error={freeEnrichmentError}
              onRun={handleBulkFreeEnrichment}
            />
            <BulkManagerActions
              selectedHotels={selectedHotels}
              providerSettings={providerSettings}
              running={bulkManagerRunning}
              summary={bulkManagerSummary}
              error={bulkManagerError}
              onRun={handleBulkManagers}
            />
            <ExportButtons hotels={hotels} context={{ location: selectedLocationName, latitude: Number(searchValues.lat), longitude: Number(searchValues.lng), radius: Number(searchValues.radius), provider: providerSettings?.hotel_provider === 'google' ? 'Google Places' : 'OpenStreetMap' }} />
            </ResultsToolbar>
            <HotelTable
              hotels={hotels}
              selectedHotelKeys={selectedHotelKeys}
              onToggleHotel={handleToggleHotel}
              selectedHotel={selectedHotel}
              onSelectHotel={setSelectedHotel}
              onView={(hotel) => setDrawerHotelKey(hotelKey(hotel))}
            />
          </>
        )}
      </section>
      <HotelDetailsDrawer hotel={drawerHotel} onClose={() => setDrawerHotelKey(null)} onEnrich={handleEnrich} onFindManagers={handleFindManagers} enriching={drawerHotel ? Boolean(enrichingHotels[hotelKey(drawerHotel)]) : false} findingManagers={drawerHotel ? Boolean(managerSearches[hotelKey(drawerHotel)]) : false} managerAvailable={Boolean(providerSettings?.apollo_enabled && providerSettings?.apollo_configured)} />
    </main>
  )
}

export default App
