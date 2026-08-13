import { useState } from 'react'
import { searchLocations } from '../locationApi.js'

function LocationSearch({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const handleSubmit = async (event) => {
    event.preventDefault()
    const cleanQuery = query.trim()
    if (cleanQuery.length < 2 || loading) {
      setMessage('Enter at least two characters to search.')
      return
    }
    setLoading(true)
    setMessage('')
    setResults([])
    try {
      const locations = await searchLocations(cleanQuery)
      setResults(locations)
      if (locations.length === 0) setMessage('No locations found.')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setLoading(false)
    }
  }

  const chooseLocation = (location) => {
    onSelect(location)
    setQuery(location.name)
    setResults([])
    setMessage('')
  }

  return (
    <section className="location-search-card" aria-label="Location search">
      <form onSubmit={handleSubmit}>
        <input value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder="Search airport, city or location..." aria-label="Search location" />
        <button type="submit" disabled={loading}>{loading ? 'Searching...' : 'Search'}</button>
      </form>
      {message && <p className="location-message">{message}</p>}
      {results.length > 0 && (
        <ul className="location-results">
          {results.map((location, index) => (
            <li key={`${location.latitude}-${location.longitude}-${index}`}>
              <button type="button" onClick={() => chooseLocation(location)}>
                <strong>{location.name}</strong>
                <span>{location.display_name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default LocationSearch
