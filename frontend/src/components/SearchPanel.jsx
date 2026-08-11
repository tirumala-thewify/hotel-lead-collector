import LocationSearch from './LocationSearch.jsx'
import SearchForm from './SearchForm.jsx'

function SearchPanel(props) {
  return (
    <section className="unified-search-card" aria-labelledby="hotel-search-title">
      <div className="panel-heading">
        <div>
          <h2 id="hotel-search-title">Search Hotels</h2>
          <p>Search an airport, city, or area and choose a radius.</p>
        </div>
      </div>
      <LocationSearch onSelect={props.onLocationSelect} />
      <SearchForm {...props} />
    </section>
  )
}

export default SearchPanel
