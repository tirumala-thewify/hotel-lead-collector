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
  fetchBusinessCategories,
  fetchNearbyHotels,
  findHotelManagers,
  findManagersBulk,
  freeEnrichHotelsBulk,
  HotelServiceError,
} from './services/hotelService.js'
import './index.css'
import { fetchProviderSettings } from './services/providerSettingsService.js'

function App() {
  const defaultCategories = [{ id: 'hotels_resorts', name: 'Hotels & Resorts' }]
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
  const [categories, setCategories] = useState(defaultCategories)
  const [selectedCategory, setSelectedCategory] = useState('hotels_resorts')
  const [categoryLoadError, setCategoryLoadError] = useState('')
  const providerName = providerSettings?.hotel_provider === 'google'
    ? 'Google Places'
    : providerSettings?.hotel_provider === 'geoapify' ? 'Geoapify' : 'OpenStreetMap'

  useEffect(() => {
    fetchProviderSettings().then(setProviderSettings).catch(() => {})
    fetchBusinessCategories()
      .then(setCategories)
      .catch(() => setCategoryLoadError('Business types could not be loaded. Hotels & Resorts remains available.'))
  }, [])

  const handleSearch = async ({ lat, lng, radius }) => {
    if (loading) return

    setLoading(true)
    setError('')
    setHasSearched(false)

    try {
      const data = await fetchNearbyHotels(lat, lng, radius, selectedCategory)
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
        setError('Business data service is temporarily unavailable. Please try again later.')
      } else {
        setError(requestError.message || 'Unable to search for businesses. Please try again.')
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

  const clearSearchResults = () => {
    setHotels([])
    setHasSearched(false)
    setError('')
    setSelectedHotelKeys([])
    setSelectedHotel(null)
    setDrawerHotelKey(null)
    setBulkManagerSummary(null)
    setFreeEnrichmentSummary(null)
  }

  const handleCategoryChange = (category) => {
    setSelectedCategory(category)
    clearSearchResults()
  }

  const handleFindManagers = async (hotel) => {
    if (selectedCategory !== 'hotels_resorts') return
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
    if (selectedCategory !== 'hotels_resorts') return
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
    if (selectedCategory !== 'hotels_resorts') return
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
    if (selectedCategory !== 'hotels_resorts') return
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
      <AppHeader providerName={providerName} />
      <SearchPanel onLocationSelect={handleLocationSelect} values={searchValues} onValuesChange={handleSearchValuesChange} onSearch={handleSearch} loading={loading} selectedLocationName={selectedLocationName} categories={categories} selectedCategory={selectedCategory} onCategoryChange={handleCategoryChange} categoryLoadError={categoryLoadError} />
      <div className="map-summary-workspace">
        <HotelMap location={{ latitude: searchValues.lat, longitude: searchValues.lng }} radius={searchValues.radius} hotels={hotels} onLocationChange={handleLocationChange} selectedHotel={selectedHotel} onSelectHotel={setSelectedHotel} />
        <SearchSummary locationName={selectedLocationName} radius={searchValues.radius} providerName={providerName} hotels={hotels} hasSearched={hasSearched} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Hotels & Resorts'} />
      </div>

      <section className="results-section" aria-live="polite" aria-busy={loading}>
        {loading && <div className="compact-alert loading-status">Searching nearby businesses...</div>}

        {!loading && error && (
          <div className="compact-alert error-status" role="alert">
            <strong>Business search temporarily unavailable.</strong>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && !hasSearched && <div className="clean-empty-state">Search a location, choose a business type and radius, then find nearby businesses.</div>}

        {!loading && !error && hasSearched && hotels.length === 0 && (
          <div className="clean-empty-state">
            <strong>No businesses found in this area.</strong>
            <span>Try increasing the radius or choosing another location.</span>
          </div>
        )}

        {!loading && !error && hasSearched && hotels.length > 0 && (
          <>
            <ResultsToolbar count={hotels.length} selectedCount={selectedHotels.length} allSelected={selectedHotels.length === hotels.length} onSelectAll={handleSelectAll} onClear={() => setSelectedHotelKeys([])} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Businesses'}>
            {selectedCategory === 'hotels_resorts' ? <>
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
            </> : <span className="action-note enrichment-limitation">Business enrichment for this category will be added in a later phase.</span>}
            <ExportButtons hotels={hotels} context={{ location: selectedLocationName, latitude: Number(searchValues.lat), longitude: Number(searchValues.lng), radius: Number(searchValues.radius), provider: providerName }} />
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
      <HotelDetailsDrawer hotel={drawerHotel} onClose={() => setDrawerHotelKey(null)} onEnrich={handleEnrich} onFindManagers={handleFindManagers} enriching={drawerHotel ? Boolean(enrichingHotels[hotelKey(drawerHotel)]) : false} findingManagers={drawerHotel ? Boolean(managerSearches[hotelKey(drawerHotel)]) : false} managerAvailable={Boolean(providerSettings?.apollo_enabled && providerSettings?.apollo_configured)} enrichmentAvailable={selectedCategory === 'hotels_resorts'} />
    </main>
  )
}

export default App
