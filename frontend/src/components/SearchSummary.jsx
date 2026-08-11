import DataCoverage from './DataCoverage.jsx'

function SearchSummary({ locationName, radius, providerName, hotels, hasSearched }) {
  const total = hotels.length
  return (
    <aside className="search-summary-card" aria-label="Search summary">
      <div>
        <span className="section-kicker">Search Summary</span>
        <h2>{locationName}</h2>
      </div>
      <dl className="summary-basics">
        <div><dt>Radius</dt><dd>{Number(radius) / 1000} km</dd></div>
        <div><dt>Provider</dt><dd>{providerName}</dd></div>
        <div><dt>Hotels</dt><dd>{hasSearched ? total : '—'}</dd></div>
      </dl>
      <DataCoverage hotels={hotels} />
    </aside>
  )
}

export default SearchSummary
