import { prepareExportBusinesses } from './homeApi.js'

export async function prepareBusinessesForExport(
  businesses,
  prepare = prepareExportBusinesses,
) {
  return prepare(businesses)
}

export const prepareHotelsForExport = prepareBusinessesForExport
