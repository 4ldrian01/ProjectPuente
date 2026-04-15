/**
 * apiErrors.js — API error normalization helpers.
 * Summary: Extracts consistent user-facing error strings from backend payload variants and validation maps.
 */

export function flattenValidationErrors(errors) {
  if (!errors || typeof errors !== 'object') {
    return ''
  }

  return Object.values(errors)
    .flat()
    .map((entry) => String(entry || '').trim())
    .filter(Boolean)
    .join(' ')
}

export function extractApiErrorMessage(payload, fallback = 'Request failed.') {
  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const directError = String(payload.error || '').trim()
  if (directError) {
    return directError
  }

  const detailError = String(payload.detail || '').trim()
  if (detailError) {
    return detailError
  }

  const validationError = flattenValidationErrors(payload.errors)
  if (validationError) {
    return validationError
  }

  return fallback
}
