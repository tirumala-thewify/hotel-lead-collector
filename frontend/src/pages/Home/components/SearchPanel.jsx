import LocationSearch from './LocationSearch.jsx'
import SearchForm from './SearchForm.jsx'

function SearchPanel(props) {
  return (
    <section className="unified-search-card" aria-labelledby="business-search-title">
      <div className="panel-heading">
        <div>
          <h2 id="business-search-title">Search Businesses</h2>
          <p>Search an airport, city, or area, then choose a business type and radius.</p>
        </div>
      </div>
      <LocationSearch onSelect={props.onLocationSelect} />
      {props.categoryLoadError && <p className="category-load-note" role="status">{props.categoryLoadError}</p>}
      <SearchForm {...props} />
    </section>
  )
}

export default SearchPanel
