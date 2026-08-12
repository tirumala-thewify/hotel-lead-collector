import { prepareExportHotels } from './hotelService.js'

export async function prepareHotelsForExport(
  hotels,
  prepare = prepareExportHotels,
) {
  return prepare(hotels)
}
