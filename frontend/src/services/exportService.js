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
const joinValues = (items, value) => (items || []).map(value).filter(Boolean).join('; ')
const roleContacts = (hotel, groups) => (hotel.decision_makers || []).filter((item) => groups.includes(item.role_group))
const roleValue = (hotel, groups, field) => joinValues(roleContacts(hotel, groups), (item) => item[field] || (field === 'email' ? item.business_email : null))
COLUMNS.push(
  ['All Business Emails', (hotel) => joinValues(hotel.business_emails, (item) => `${item.email} [${item.type || 'other'}]`)],
  ['Business Email Source URLs', (hotel) => joinValues(hotel.business_emails, (item) => item.source_url)],
  ['All Business Phones', (hotel) => joinValues(hotel.business_phones, (item) => `${item.phone} [${item.type || 'general'}]`)],
  ['Business Phone Source URLs', (hotel) => joinValues(hotel.business_phones, (item) => item.source_url)],
  ['LinkedIn', (hotel) => hotel.social_profiles?.linkedin],
  ['LinkedIn Source URL', (hotel) => hotel.social_profile_sources?.linkedin],
  ['Facebook', (hotel) => hotel.social_profiles?.facebook],
  ['Facebook Source URL', (hotel) => hotel.social_profile_sources?.facebook],
  ['Instagram', (hotel) => hotel.social_profiles?.instagram],
  ['Instagram Source URL', (hotel) => hotel.social_profile_sources?.instagram],
  ['Decision Makers', (hotel) => joinValues(hotel.decision_makers, (item) => `${item.name || 'Team'} — ${item.title}`)],
  ['Decision Maker Source URLs', (hotel) => joinValues(hotel.decision_makers, (item) => item.source_url)],
)
for (const [label, groups] of [
  ['General Manager', ['general_manager']],
  ['IT Director / Head of IT', ['it_leadership', 'it_management']],
  ['CIO / CTO', ['executive']],
  ['Director of Operations', ['operations']],
  ['Sales Contact', ['sales']],
]) {
  COLUMNS.push(
    [label, (hotel) => roleValue(hotel, groups, 'name')],
    [`${label} Email`, (hotel) => roleValue(hotel, groups, 'email')],
    [`${label} Phone`, (hotel) => roleValue(hotel, groups, 'phone')],
  )
}
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

export function buildHotelsCsv(hotels, context) {
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
  return `\uFEFF${rows.join('\r\n')}`
}

export function exportHotelsCsv(hotels, context) {
  const blob = new Blob([buildHotelsCsv(hotels, context)], { type: 'text/csv;charset=utf-8' })
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
