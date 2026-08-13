import { useEffect, useState } from 'react'
import BusinessTable from './components/BusinessTable.jsx'
import BusinessMap from './components/BusinessMap.jsx'
import ExportButtons from './components/ExportButtons.jsx'
import BulkManagerActions from './components/BulkManagerActions.jsx'
import FreeEnrichmentActions from './components/FreeEnrichmentActions.jsx'
import AppHeader from './components/AppHeader.jsx'
import SearchPanel from './components/SearchPanel.jsx'
import SearchSummary from './components/SearchSummary.jsx'
import ResultsToolbar from './components/ResultsToolbar.jsx'
import BusinessDetailsDrawer from './components/BusinessDetailsDrawer.jsx'
import {
  enrichBusiness,
  fetchBusinessCategories,
  fetchNearbyBusinesses,
  findDecisionMakers,
  findDecisionMakersBulk,
  freeEnrichBusinessesBulk,
  HotelServiceError,
} from './homeApi.js'
import '../../index.css'
import { fetchProviderSettings } from '../../shared/api/providerSettingsApi.js'
import { businessKey } from './businessIdentity.js'

// ============================================================
// DECISION MAKER DISCOVERY
// Normalizes configured-provider results before they enter Home state.
// ============================================================

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

function HomePage() {
  // ------------------------------------------------------------
  // STATE
  // Owns business search, selection, enrichment, and export state.
  // ------------------------------------------------------------
  const defaultCategories = [{ id: 'hotels_resorts', name: 'Hotels & Resorts' }]
  const [businesses, setBusinesses] = useState([])
  const [hasSearched, setHasSearched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [enrichingBusinesses, setEnrichingBusinesses] = useState({})
  const [managerSearches, setManagerSearches] = useState({})
  const [providerSettings, setProviderSettings] = useState(null)
  const [selectedProviders, setSelectedProviders] = useState([])
  const [selectedPeopleProviders, setSelectedPeopleProviders] = useState([])
  const [searchedProviders, setSearchedProviders] = useState([])
  const [providerWarning, setProviderWarning] = useState('')
  const [selectedBusinessKeys, setSelectedBusinessKeys] = useState([])
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
  const [selectedBusiness, setSelectedBusiness] = useState(null)
  const [drawerBusinessKey, setDrawerBusinessKey] = useState(null)
  const [selectedLocationName, setSelectedLocationName] = useState('Delhi Airport')
  const [categories, setCategories] = useState(defaultCategories)
  const [selectedCategory, setSelectedCategory] = useState('hotels_resorts')
  const [categoryLoadError, setCategoryLoadError] = useState('')
  const providerLabels = { openstreetmap: 'OpenStreetMap', geoapify: 'Geoapify', google: 'Google Places', playwright: 'Browser Search' }
  const peopleProviderLabels = { official_website: 'Official Website', apollo: 'Apollo', zoominfo: 'ZoomInfo' }
  const availableProviders = (providerSettings?.business_providers || []).map((id) => ({ id, name: providerLabels[id] }))
  const providerNames = (searchedProviders.length ? searchedProviders : selectedProviders)
    .map((provider) => providerLabels[provider])

  // ------------------------------------------------------------
  // DATA LOADING
  // Loads configured providers and supported business categories.
  // ------------------------------------------------------------
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

  // ============================================================
  // BUSINESS SEARCH
  // Handles location/category search and result loading.
  // ============================================================
  const handleSearch = async ({ lat, lng, radius }) => {
    if (loading) return

    setLoading(true)
    setError('')
    setProviderWarning('')
    setHasSearched(false)

    try {
      const data = await fetchNearbyBusinesses(lat, lng, radius, selectedCategory, selectedProviders)
      setBusinesses(data.hotels.map((business) => ({
        ...business,
        category: business.category || data.category || selectedCategory,
      })))
      setSelectedBusinessKeys([])
      setBulkManagerSummary(null)
      setFreeEnrichmentSummary(null)
      setSelectedBusiness(null)
      setDrawerBusinessKey(null)
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
      setBusinesses([])
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
    setSelectedBusiness(null)
    setSelectedLocationName('Selected map location')
  }

  const handleLocationSelect = (location) => {
    setSelectedLocationName(location.name || location.display_name || 'Selected location')
    setSearchValues((current) => ({
      ...current,
      lat: Number(location.latitude).toFixed(6),
      lng: Number(location.longitude).toFixed(6),
    }))
    setSelectedBusiness(null)
  }

  const handleSearchValuesChange = (values) => {
    if (values.lat !== searchValues.lat || values.lng !== searchValues.lng) {
      setSelectedLocationName('Custom coordinates')
    }
    setSearchValues(values)
  }

  const clearSearchResults = () => {
    setBusinesses([])
    setHasSearched(false)
    setError('')
    setSelectedBusinessKeys([])
    setSelectedBusiness(null)
    setDrawerBusinessKey(null)
    setBulkManagerSummary(null)
    setFreeEnrichmentSummary(null)
  }

  const handleCategoryChange = (category) => {
    setSelectedCategory(category)
    clearSearchResults()
  }

  // ============================================================
  // DECISION MAKER DISCOVERY
  // Handles single and bulk configured people-provider workflows.
  // ============================================================
  const handleFindManagers = async (business) => {
    if (!selectedPeopleProviders.length) return
    const key = businessKey(business)
    if (managerSearches[key]) return
    setManagerSearches((current) => ({ ...current, [key]: true }))
    try {
      const result = await findDecisionMakers(business, selectedPeopleProviders)
      const contacts = normalizeDecisionMakers(result.contacts)
      setBusinesses((current) => current.map((item) => (
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
      setBusinesses((current) => current.map((item) => (
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

  const selectedBusinesses = businesses.filter((business) => selectedBusinessKeys.includes(businessKey(business)))
  const drawerBusiness = businesses.find((business) => businessKey(business) === drawerBusinessKey) || null

  const handleToggleBusiness = (key) => {
    setSelectedBusinessKeys((current) => current.includes(key)
      ? current.filter((item) => item !== key)
      : [...current, key])
  }

  const handleSelectAll = (checked) => {
    setSelectedBusinessKeys(checked ? businesses.map(businessKey) : [])
  }

  const handleBulkManagers = async () => {
    if (!selectedPeopleProviders.length) return
    if (!selectedBusinesses.length || selectedBusinesses.length > 10 || bulkManagerRunning) return
    setBulkManagerRunning(true)
    setBulkManagerError('')
    setBulkManagerSummary(null)
    try {
      const data = await findDecisionMakersBulk(selectedBusinesses, selectedPeopleProviders)
      const resultsByIdentity = new Map()
      for (const result of data.results) {
        const identity = `${result.business_name || result.hotel_name}|${result.category || 'hotels_resorts'}`
        const matches = resultsByIdentity.get(identity) || []
        matches.push(result)
        resultsByIdentity.set(identity, matches)
      }
      setBusinesses((current) => current.map((business) => {
        if (!selectedBusinessKeys.includes(businessKey(business))) return business
        const identity = `${business.name}|${business.category || 'hotels_resorts'}`
        const result = resultsByIdentity.get(identity)?.shift()
        if (!result) return business
        const contacts = normalizeDecisionMakers(result.contacts)
        return {
          ...business,
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

  // ============================================================
  // OFFICIAL WEBSITE ENRICHMENT
  // Merges free public website contacts into selected businesses.
  // ============================================================
  const handleBulkFreeEnrichment = async () => {
    if (selectedCategory !== 'hotels_resorts') return
    if (!selectedBusinesses.length || selectedBusinesses.length > 10 || freeEnrichmentRunning) return
    setFreeEnrichmentRunning(true)
    setFreeEnrichmentError('')
    setFreeEnrichmentSummary(null)
    try {
      const data = await freeEnrichBusinessesBulk(selectedBusinesses)
      const resultsByName = new Map(data.results.map((result) => [result.hotel_name, result]))
      setBusinesses((current) => current.map((business) => {
        const result = resultsByName.get(business.name)
        if (!result || !selectedBusinessKeys.includes(businessKey(business))) return business
        return {
          ...business,
          ...result.hotel,
          enrichment_status: result.status,
          enrichment_message: result.status === 'ERROR' ? 'Free enrichment failed for this business.' : '',
          enrichment_sources: result.sources,
          website_confidence: result.website_confidence,
          business_emails: result.business_emails || [],
          business_phones: result.business_phones || [],
          whatsapp_contacts: result.whatsapp_contacts || [],
          social_profiles: result.social_profiles || {},
          social_profile_sources: result.social_profile_sources || {},
          discovered_pages: result.discovered_pages || {},
          decision_makers: result.decision_makers || business.decision_makers || [],
        }
      }))
      setFreeEnrichmentSummary(data.summary)
    } catch (freeError) {
      setFreeEnrichmentError(freeError.message)
    } finally {
      setFreeEnrichmentRunning(false)
    }
  }

  const handleEnrich = async (business) => {
    if (selectedCategory !== 'hotels_resorts') return
    const key = businessKey(business)
    if (enrichingBusinesses[key]) return
    setEnrichingBusinesses((current) => ({ ...current, [key]: true }))

    try {
      const enriched = await enrichBusiness(business)
      setBusinesses((current) => current.map((item) => {
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
          business_emails: enriched.business_emails || [],
          business_phones: enriched.business_phones || [],
          whatsapp_contacts: enriched.whatsapp_contacts || [],
          social_profiles: enriched.social_profiles || {},
          social_profile_sources: enriched.social_profile_sources || {},
          discovered_pages: enriched.discovered_pages || {},
          decision_makers: enriched.decision_makers || item.decision_makers || [],
        }
      }))
    } catch (enrichmentError) {
      setBusinesses((current) => current.map((item) => (
        businessKey(item) === key
          ? { ...item, enrichment_status: 'ERROR', enrichment_message: enrichmentError.message }
          : item
      )))
    } finally {
      setEnrichingBusinesses((current) => ({ ...current, [key]: false }))
    }
  }

  // ============================================================
  // ENRICHED EXPORT
  // Retains automatically enriched CSV/Excel results in Home state.
  // ============================================================
  const handleExportEnriched = (enrichedBusinesses) => {
    setBusinesses((current) => current.map((business, index) => (
      enrichedBusinesses[index] ? { ...business, ...enrichedBusinesses[index] } : business
    )))
  }

  // ------------------------------------------------------------
  // RENDER
  // ------------------------------------------------------------
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
          {peopleProviderLabels[provider] || provider}
        </label>)}
        {!providerSettings?.people_providers?.length && <span>Configure a people enrichment provider in Settings.</span>}
      </fieldset>
      <div className="map-summary-workspace">
        <BusinessMap location={{ latitude: searchValues.lat, longitude: searchValues.lng }} radius={searchValues.radius} businesses={businesses} onLocationChange={handleLocationChange} selectedBusiness={selectedBusiness} onSelectBusiness={setSelectedBusiness} />
        <SearchSummary locationName={selectedLocationName} radius={searchValues.radius} providerNames={providerNames} businesses={businesses} hasSearched={hasSearched} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Hotels & Resorts'} />
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

        {!loading && !error && hasSearched && businesses.length === 0 && (
          <div className="clean-empty-state">
            <strong>No businesses found in this area.</strong>
            <span>Try increasing the radius or choosing another location.</span>
          </div>
        )}

        {!loading && !error && hasSearched && businesses.length > 0 && (
          <>
            <ResultsToolbar count={businesses.length} selectedCount={selectedBusinesses.length} allSelected={selectedBusinesses.length === businesses.length} onSelectAll={handleSelectAll} onClear={() => setSelectedBusinessKeys([])} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Businesses'}>
            {selectedCategory === 'hotels_resorts' && <FreeEnrichmentActions
              selectedBusinesses={selectedBusinesses}
              running={freeEnrichmentRunning}
              summary={freeEnrichmentSummary}
              error={freeEnrichmentError}
              onRun={handleBulkFreeEnrichment}
            />}
            <BulkManagerActions
              selectedBusinesses={selectedBusinesses}
              providerSettings={providerSettings}
              running={bulkManagerRunning}
              summary={bulkManagerSummary}
              error={bulkManagerError}
              onRun={handleBulkManagers}
            />
            {selectedCategory !== 'hotels_resorts' && <span className="action-note enrichment-limitation">Business contact enrichment for this category will be added in a later phase.</span>}
            <ExportButtons businesses={businesses} onEnriched={handleExportEnriched} context={{ location: selectedLocationName, latitude: Number(searchValues.lat), longitude: Number(searchValues.lng), radius: Number(searchValues.radius), provider: providerNames.join(' + ') }} />
            </ResultsToolbar>
            <BusinessTable
              businesses={businesses}
              selectedBusinessKeys={selectedBusinessKeys}
              onToggleBusiness={handleToggleBusiness}
              selectedBusiness={selectedBusiness}
              onSelectBusiness={setSelectedBusiness}
              onView={(business) => setDrawerBusinessKey(businessKey(business))}
            />
          </>
        )}
      </section>
      <BusinessDetailsDrawer business={drawerBusiness} categoryName={categories.find((category) => category.id === selectedCategory)?.name || 'Business'} onClose={() => setDrawerBusinessKey(null)} onEnrich={handleEnrich} onFindManagers={handleFindManagers} enriching={drawerBusiness ? Boolean(enrichingBusinesses[businessKey(drawerBusiness)]) : false} findingManagers={drawerBusiness ? Boolean(managerSearches[businessKey(drawerBusiness)]) : false} apolloEnabled={Boolean(selectedPeopleProviders.length)} apolloConfigured={Boolean(selectedPeopleProviders.length)} enrichmentAvailable={selectedCategory === 'hotels_resorts'} />
    </main>
  )
}

export default HomePage
