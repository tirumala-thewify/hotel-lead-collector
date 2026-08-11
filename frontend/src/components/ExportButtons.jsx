import { useState } from 'react'
import { exportHotelsCsv, exportHotelsExcel } from '../services/exportService.js'

function ExportButtons({ hotels, context }) {
  const [preparingExcel, setPreparingExcel] = useState(false)
  const [error, setError] = useState('')
  const disabled = hotels.length === 0

  const handleExcel = async () => {
    if (disabled || preparingExcel) return
    setPreparingExcel(true)
    setError('')
    try {
      await exportHotelsExcel(hotels, context)
    } catch (exportError) {
      setError(exportError.message)
    } finally {
      setPreparingExcel(false)
    }
  }

  return (
    <div className="export-area">
      <div className="export-buttons">
        <button type="button" disabled={disabled} onClick={() => exportHotelsCsv(hotels, context)}>
          Export CSV
        </button>
        <button type="button" disabled={disabled || preparingExcel} onClick={handleExcel}>
          {preparingExcel ? 'Preparing Excel...' : 'Export Excel'}
        </button>
      </div>
      {error && <span role="alert">{error}</span>}
    </div>
  )
}

export default ExportButtons
