import { useState } from 'react'

function validate(values) {
  const errors = {}
  const latitude = Number(values.lat)
  const longitude = Number(values.lng)
  const radius = Number(values.radius)

  if (values.lat.trim() === '' || !Number.isFinite(latitude)) {
    errors.lat = 'Enter a valid latitude.'
  } else if (latitude < -90 || latitude > 90) {
    errors.lat = 'Latitude must be between -90 and 90.'
  }

  if (values.lng.trim() === '' || !Number.isFinite(longitude)) {
    errors.lng = 'Enter a valid longitude.'
  } else if (longitude < -180 || longitude > 180) {
    errors.lng = 'Longitude must be between -180 and 180.'
  }

  if (values.radius.trim() === '' || !Number.isFinite(radius)) {
    errors.radius = 'Enter a valid radius.'
  } else if (radius <= 0) {
    errors.radius = 'Radius must be greater than 0.'
  } else if (radius > 20000) {
    errors.radius = 'Radius cannot exceed 20,000 metres.'
  }

  return { errors, latitude, longitude, radius }
}

function SearchForm({ values, onValuesChange, onSearch, loading, selectedLocationName, categories, selectedCategory, onCategoryChange }) {
  const [errors, setErrors] = useState({})
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const handleChange = (event) => {
    const { name, value } = event.target
    onValuesChange({ ...values, [name]: value })
    setErrors((current) => ({ ...current, [name]: undefined }))
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    const result = validate(values)
    setErrors(result.errors)

    if (Object.keys(result.errors).length === 0) {
      onSearch({ lat: result.latitude, lng: result.longitude, radius: result.radius })
    }
  }

  return (
    <form className="compact-search-form" onSubmit={handleSubmit} noValidate>
      <div className="selected-location-line">
        <span aria-hidden="true">📍</span>
        <strong title={selectedLocationName}>{selectedLocationName}</strong>
      </div>
      <div className="search-controls">
        <div className="field-group category-field">
          <label htmlFor="business-category">Business Type</label>
          <select id="business-category" value={selectedCategory} onChange={(event) => onCategoryChange(event.target.value)} disabled={loading}>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
        </div>
        <div className="field-group radius-field">
          <label htmlFor="radius">Radius</label>
          <select id="radius" name="radius" value={values.radius} onChange={handleChange} disabled={loading}>
            <option value="1000">1 km</option><option value="2000">2 km</option>
            <option value="3000">3 km</option><option value="5000">5 km</option>
            <option value="10000">10 km</option><option value="15000">15 km</option>
            <option value="20000">20 km</option>
          </select>
        </div>
        <button className="search-button" type="submit" disabled={loading}>
          {loading ? 'Searching...' : 'Find Businesses'}
        </button>
      </div>
      <button type="button" className="advanced-toggle" onClick={() => setAdvancedOpen((current) => !current)} aria-expanded={advancedOpen}>
        Advanced Search <span aria-hidden="true">{advancedOpen ? '▴' : '▾'}</span>
      </button>
      {advancedOpen && <div className="advanced-fields">
        <div className="field-group">
          <label htmlFor="lat">Latitude</label>
          <input
            id="lat"
            name="lat"
            type="number"
            step="any"
            value={values.lat}
            onChange={handleChange}
            aria-invalid={Boolean(errors.lat)}
            aria-describedby={errors.lat ? 'lat-error' : undefined}
            disabled={loading}
          />
          {errors.lat && <span id="lat-error" className="field-error">{errors.lat}</span>}
        </div>
        <div className="field-group">
          <label htmlFor="lng">Longitude</label>
          <input
            id="lng"
            name="lng"
            type="number"
            step="any"
            value={values.lng}
            onChange={handleChange}
            aria-invalid={Boolean(errors.lng)}
            aria-describedby={errors.lng ? 'lng-error' : undefined}
            disabled={loading}
          />
          {errors.lng && <span id="lng-error" className="field-error">{errors.lng}</span>}
        </div>
      </div>}
      {errors.radius && <span id="radius-error" className="field-error">{errors.radius}</span>}
    </form>
  )
}

export default SearchForm
