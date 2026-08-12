import { useState } from 'react'
import { exportHotelsCsv, exportHotelsExcel } from '../services/exportService.js'
import { prepareHotelsForExport } from '../services/exportEnrichmentService.js'

function ExportButtons({ hotels, context, onEnriched }) {
  const [preparing, setPreparing] = useState(null)
  const [error, setError] = useState('')
  const [complete, setComplete] = useState('')
  const disabled = hotels.length === 0 || Boolean(preparing)

  const handleExport = async (format) => {
    if (disabled) return
    setPreparing(format)
    setError('')
    setComplete('')
    try {
      const enrichedHotels = await prepareHotelsForExport(hotels)
      onEnriched?.(enrichedHotels)
      if (format === 'csv') exportHotelsCsv(enrichedHotels, context)
      else await exportHotelsExcel(enrichedHotels, context)
      setComplete(`${format.toUpperCase()} export prepared.`)
    } catch (exportError) {
      setError(exportError.message)
    } finally {
      setPreparing(null)
    }
  }

  return (
    <div className="export-area">
      <div className="export-buttons">
        <button type="button" disabled={disabled} onClick={() => handleExport('csv')}>
          {preparing === 'csv' ? 'Preparing enriched export...' : 'Export CSV'}
        </button>
        <button type="button" disabled={disabled} onClick={() => handleExport('excel')}>
          {preparing === 'excel' ? 'Preparing enriched export...' : 'Export Excel'}
        </button>
      </div>
      {error && <span role="alert">{error}</span>}
      {complete && <span role="status">{complete}</span>}
    </div>
  )
}

export default ExportButtons
