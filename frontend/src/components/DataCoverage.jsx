const FIELDS = ['address', 'phone', 'email', 'website', 'brand']

function DataCoverage({ hotels }) {
  const total = hotels.length
  return (
    <div className="coverage-list" aria-label="Data coverage">
      <strong>Data coverage</strong>
      {FIELDS.map((field) => {
        const available = hotels.filter((hotel) => Boolean(hotel[field])).length
        const percent = total ? Math.round((available / total) * 100) : 0
        return <div className="coverage-item" key={field}>
          <span>{field[0].toUpperCase() + field.slice(1)}</span><span>{available}/{total}</span><span>{percent}%</span>
          <i><b style={{ width: `${percent}%` }} /></i>
        </div>
      })}
    </div>
  )
}

export default DataCoverage
