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
  findDecisionMakers,
  findDecisionMakersBulk,
  freeEnrichHotelsBulk,
  HotelServiceError,
} from './services/hotelService.js'
import './index.css'
import { fetchProviderSettings } from './services/providerSettingsService.js'
import { businessKey } from './businessIdentity.js'

function decisionMakerKey(contact) {
  return contact.id || [
    contact.name,
    contact.title,
    contact.organization_name || contact.company,
  ].map((value) => String(value || '').trim().toLowerCase()).join('|')
}

function normalizeDecisionMakers(contacts) {
  const unique = new Map()
  for (const contact of Array.isArray(contacts) ? contacts : []) {
    if (!contact || typeof contact !== 'object') continue
    const key = decisionMakerKey(contact)
    if (!unique.has(key)) unique.set(key, contact)
    if (unique.size === 3) break
  }
  return [...unique.values()]
}

function decisionMakerMessage(status) {
  if (status === 'FOUND') return 'Decision-makers found.'
  if (status === 'PARTIAL') return 'Partial decision-maker information found.'
  if (status === 'NOT_FOUND') return 'No matching decision-makers found.'
  if (status === 'DISABLED') return 'Apollo is disabled in Settings.'
  return 'Unable to retrieve decision-maker information.'
}

function App() {
  const defaultCategories = [{ id: 'hotels_resorts', name: 'Hotels & Resorts' }]
  const [hotels, setHotels] = useState([])
  const [hasSearched, setHasSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [enrichingHotels, setEnrichingHotels] = useState({})
  const [managerSearches, setManagerSearches] = useState({})
  const [providerSettings, setProviderSettings] = useState(null)
  const [selectedProviders, setSelectedProviders] = useState([])
  const [selectedPeopleProviders, setSelectedPeopleProviders] = useState([])
  const [searchedProviders, setSearchedProviders] = useState([])
  const [providerWarning, setProviderWarning] = useState('')
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
  const providerLabels = { openstreetmap: 'OpenStreetMap', geoapify: 'Geoapify', google: 'Google Places', playwright: 'Browser Search' }
  const availableProviders = (providerSettings?.business_providers || []).map((id) => ({ id, name: providerLabels[id] }))
  const providerNames = (searchedProviders.length ? searchedProviders : selectedProviders)
    .map((provider) => providerLabels[provider])

  useEffect(() => {
    fetchProviderSettings().then((settings) => {
      setProviderSettings(settings)
      setSelectedProviders(settings.business_providers || [settings.hotel_provider])
      setSelectedPeopleProviders(settings.people_providers || [])
    }).catch(() => {})
    fetchBusinessCategories()
      .then(setCategories)
      .catch(() => setCategoryLoadError('Business types could not be loaded. Hotels & Resorts remains available.'))
  }, [])

  const handleSearch = async ({ lat, lng, radius }) => {
    if (loading) return

    setLoading(true)
    setError('')
    setProviderWarning('')
    setHasSearched(false)

    try {
      const data = await fetchNearbyHotels(lat, lng, radius, selectedCategory, selectedProviders)
      setHotels(data.hotels.map((business) => ({
        ...business,
        category: business.category || data.category || selectedCategory,
      })))
      setSelectedHotelKeys([])
      setBulkManagerSummary(null)
      setFreeEnrichmentSummary(null)
      setSelectedHotel(null)
      setDrawerHotelKey(null)
      setHasSearched(true)
      setSearchedProviders(data.providers || selectedProviders)
      const failed = Object.entries(data.provider_results || {})
        .filter(([, result]) => result.status === 'error').map(([provider]) => providerLabels[provider])
      if (failed.length) {
        const succeeded = Object.entries(data.provider_results).filter(([, result]) => result.status === 'success')
          .map(([provider]) => providerLabels[provider])
        setProviderWarning(`${failed.join(' + ')} was unavailable. Results shown from ${succeeded.join(' + ')}.`)
      }
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
    if (!selectedPeopleProviders.length) return
    const key = businessKey(hotel)
    if (managerSearches[key]) return
    setManagerSearches((current) => ({ ...current, [key]: true }))
    try {
      const result = await findDecisionMakers(hotel, selectedPeopleProviders)
      const contacts = normalizeDecisionMakers(result.contacts)
      setHotels((current) => current.map((item) => (
        businessKey(item) === key
          ? {
              ...item,
              decision_makers: contacts,
              manager_contacts: contacts,
              manager_status: result.status,
              manager_message: decisionMakerMessage(result.status),
            }
          : item
      )))
    } catch {
      setHotels((current) => current.map((item) => (
        businessKey(item) === key
          ? {
              ...item,
              decision_makers: [],
              manager_contacts: [],
              manager_status: 'ERROR',
              manager_message: 'Unable to retrieve decision-maker information.',
            }
          : item
      )))
    } finally {
      setManagerSearches((current) => ({ ...current, [key]: false }))
    }
  }

  const selectedHotels = hotels.filter((hotel) => selectedHotelKeys.includes(businessKey(hotel)))
  const drawerHotel = hotels.find((hotel) => businessKey(hotel) === drawerHotelKey) || null

  const handleToggleHotel = (key) => {
    setSelectedHotelKeys((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key])
  }

  const handleSelectAll = (checked) => {
    setSelectedHotelKeys(checked ? hotels.map(businessKey) : [])
  }

  const handleBulkManagers = async () => {
    if (!selectedPeopleProviders.length) return
    if (!selectedHotels.length || selectedHotels.length > 10 || bulkManagerRunning) return
    setBulkManagerRunning(true)
    setBulkManagerError('')
    setBulkManagerSummary(null)
    try {
      const data = await findDecisionMakersBulk(selectedHotels, selectedPeopleProviders)
      const resultsByIdentity = new Map()
      for (const result of data.results) {
        const identity = `${result.business_name || result.hotel_name}|${result.category || 'hotels_resorts'}`
        const matches = resultsByIdentity.get(identity) || []
        matches.push(result)
        resultsByIdentity.set(identity, matches)
      }
      setHotels((current) => current.map((hotel) => {
        if (!selectedHotelKeys.includes(businessKey(hotel))) return hotel
        const identity = `${hotel.name}|${hotel.category || 'hotels_resorts'}`
        const result = resultsByIdentity.get(identity)?.shift()
        if (!result) return hotel
        const contacts = normalizeDecisionMakers(result.contacts)
        return {
          ...hotel,
          decision_makers: contacts,
          manager_contacts: contacts,
          manager_status: result.status,
          manager_message: decisionMakerMessage(result.status),
        }
      }))
      setBulkManagerSummary(data.summary)
    } catch {
      setBulkManagerError('Unable to retrieve decision-maker information.')
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
        if (!result || !selectedHotelKeys.includes(businessKey(hotel))) return hotel
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
    const key = businessKey(hotel)
    if (enrichingHotels[key]) return
    setEnrichingHotels((current) => ({ ...current, [key]: true }))

    try {
      const enriched = await enrichHotel(hotel)
      setHotels((current) => current.map((item) => {
        if (businessKey(item) !== key) return item
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
        businessKey(item) === key
          ? { ...item, enrichment_status: 'ERROR', enrichment_message: enrichmentError.message }
          : item
      )))
    } finally {
      setEnrichingHotels((current) => ({ ...current, [key]: false }))
    }
  }

  return (
    <main className="app-shell">
      <AppHeader providerName={providerNames.join(' + ')} />
      <SearchPanel onLocationSelect={handleLocationSelect} values={searchValues} onValuesChange={handleSearchValuesChange} onSearch={handleSearch} loading={loading} selectedLocationName={selectedLocationName} categories={categories} selectedCategory={selectedCategory} onCategoryChange={handleCategoryChange} categoryLoadError={categoryLoadError} availableProviders={availableProviders} selectedProviders={selectedProviders} onProvidersChange={setSelectedProviders} />
      <fieldset className="people-provider-selector">
        <legend>Decision-maker providers</legend>
        {(providerSettings?.people_providers || []).map((provider) => <label key={provider}>
          <input type="checkbox" checked={selectedPeopleProviders.includes(provider)}
            onChange={() => setSelectedPeopleProviders(selectedPeopleProviders.includes(provider)
              ? selectedPeopleProviders.filter((item) => item !== provider)
              : [...selectedPeopleProviders, provider])} />
          {provider === 'zoominfo' ? 'ZoomInfo' : 'Apollo'}
        </label>)}
        {!providerSettings?.people_providers?.length && <span>Configure a people enrichment provider in Settings.</span>}
      </fieldset>
      <div className="map-summary-workspace">
        <HotelMap location={{ latitude: searchValues.lat, longitude: searchValues.lng }} radius={searchValues.radius} hotels={hotels} onLocationChange={handleLocationChange} selectedHotel={selectedHotel} onSelectHotel={setSelectedHotel} />
        <SearchSummary locationName={selectedLocationName} radius={searchValues.radius} providerNames={providerNames} hotels={hotels} hasSearched={hasSearched} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Hotels & Resorts'} />
      </div>

      <section className="results-section" aria-live="polite" aria-busy={loading}>
        {loading && <div className="compact-alert loading-status">Searching nearby businesses...</div>}
        {!loading && providerWarning && <div className="compact-alert loading-status" role="status">{providerWarning}</div>}

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
            {selectedCategory === 'hotels_resorts' && <FreeEnrichmentActions
              selectedHotels={selectedHotels}
              running={freeEnrichmentRunning}
              summary={freeEnrichmentSummary}
              error={freeEnrichmentError}
              onRun={handleBulkFreeEnrichment}
            />}
            <BulkManagerActions
              selectedHotels={selectedHotels}
              providerSettings={providerSettings}
              running={bulkManagerRunning}
              summary={bulkManagerSummary}
              error={bulkManagerError}
              onRun={handleBulkManagers}
            />
            {selectedCategory !== 'hotels_resorts' && <span className="action-note enrichment-limitation">Business contact enrichment for this category will be added in a later phase.</span>}
            <ExportButtons hotels={hotels} context={{ location: selectedLocationName, latitude: Number(searchValues.lat), longitude: Number(searchValues.lng), radius: Number(searchValues.radius), provider: providerNames.join(' + ') }} />
            </ResultsToolbar>
            <HotelTable
              hotels={hotels}
              selectedHotelKeys={selectedHotelKeys}
              onToggleHotel={handleToggleHotel}
              selectedHotel={selectedHotel}
              onSelectHotel={setSelectedHotel}
              onView={(hotel) => setDrawerHotelKey(businessKey(hotel))}
            />
          </>
        )}
      </section>
      <HotelDetailsDrawer hotel={drawerHotel} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Business'} onClose={() => setDrawerHotelKey(null)} onEnrich={handleEnrich} onFindManagers={handleFindManagers} enriching={drawerHotel ? Boolean(enrichingHotels[businessKey(drawerHotel)]) : false} findingManagers={drawerHotel ? Boolean(managerSearches[businessKey(drawerHotel)]) : false} apolloEnabled={Boolean(selectedPeopleProviders.length)} apolloConfigured={Boolean(selectedPeopleProviders.length)} enrichmentAvailable={selectedCategory === 'hotels_resorts'} />
    </main>
  )
}

export default App
