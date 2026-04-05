const CLIENT_API_KEY = (import.meta.env.VITE_PUENTE_API_KEY || '').trim()

export function isClientApiKeyConfigured() {
  return CLIENT_API_KEY.length > 0
}

export function withApiKeyHeaders(headers = {}) {
  if (!CLIENT_API_KEY) return headers
  return {
    ...headers,
    'X-API-Key': CLIENT_API_KEY,
  }
}
