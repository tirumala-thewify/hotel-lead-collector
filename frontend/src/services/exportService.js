const EXCEL_EXPORT_URL = 'http://127.0.0.1:8000/api/hotels/export/excel/'

const BASE_COLUMNS = [
  ['S.No', (_, index) => index + 1],
  ['Hotel Name', (hotel) => hotel.name],
  ['Distance from Search Location (km)', (hotel) => hotel.distance_km],
  ['Address', (hotel) => hotel.address],
  ['Phone', (hotel) => hotel.phone],
  ['Email', (hotel) => hotel.email],
  ['Website', (hotel) => hotel.website],
  ['Brand', (hotel) => hotel.brand],
  ['Stars', (hotel) => hotel.stars],
  ['Latitude', (hotel) => hotel.latitude],
  ['Longitude', (hotel) => hotel.longitude],
  ['Source', (hotel) => hotel.source],
  ['Enrichment Status', (hotel) => hotel.enrichment_status],
]

const MANAGER_GROUPS = [
  ['General Manager', 'General Management'],
  ['Marketing Manager', 'Marketing'],
  ['IT Manager', 'Information Technology'],
]

function manager(hotel, department) {
  return hotel.manager_contacts?.find((contact) => contact.department === department) || {}
}

const COLUMNS = [...BASE_COLUMNS]
for (const [label, department] of MANAGER_GROUPS) {
  COLUMNS.push(
    [`${label} Name`, (hotel) => manager(hotel, department).name],
    [`${label} Title`, (hotel) => manager(hotel, department).title],
    [`${label} Email`, (hotel) => manager(hotel, department).email],
    [`${label} Phone`, (hotel) => manager(hotel, department).phone],
    [`${label} LinkedIn`, (hotel) => manager(hotel, department).linkedin_url],
  )
}
for (const field of ['address', 'phone', 'email', 'website', 'brand']) {
  COLUMNS.push([
    `${field[0].toUpperCase() + field.slice(1)} Source`,
    (hotel) => hotel.enrichment_sources?.[field],
  ])
}

function safeText(value) {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return /^[=+\-@]/.test(text.trimStart()) ? `'${text}` : text
}

function csvCell(value) {
  return `"${safeText(value).replaceAll('"', '""')}"`
}

function slug(value) {
  return String(value || '').toLowerCase().normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80)
}

function dateStamp() {
  return new Date().toISOString().slice(0, 10)
}

function filename(extension, location) {
  const locationSlug = slug(location)
  return `hotel-leads-${locationSlug ? `${locationSlug}-` : ''}${dateStamp()}.${extension}`
}

function download(blob, name) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function exportHotelsCsv(hotels, context) {
  const summary = [
    ['Search Location', context.location],
    ['Search Latitude', context.latitude],
    ['Search Longitude', context.longitude],
    ['Search Radius', context.radius],
    ['Hotel Data Provider', context.provider],
    ['Total Hotels', hotels.length],
    ['Exported At', new Date().toISOString()],
  ]
  const rows = [
    ...summary.map((row) => row.map(csvCell).join(',')),
    '',
    COLUMNS.map(([header]) => csvCell(header)).join(','),
    ...hotels.map((hotel, index) => (
      COLUMNS.map(([, getValue]) => csvCell(getValue(hotel, index))).join(',')
    )),
  ]
  const blob = new Blob([`\uFEFF${rows.join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
  download(blob, filename('csv', context.location))
}

export async function exportHotelsExcel(hotels, context) {
  let response
  try {
    response = await fetch(EXCEL_EXPORT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hotels, context }),
    })
  } catch {
    throw new Error('Unable to export hotel data. Please try again.')
  }
  if (!response.ok) {
    throw new Error('Unable to export hotel data. Please try again.')
  }
  download(await response.blob(), filename('xlsx', context.location))
}
