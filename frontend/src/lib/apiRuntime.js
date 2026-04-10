const PROJECTPUENTE_LOCAL_HOST = 'projectpuente.local'
const DEFAULT_FRONTEND_PORT = '5173'
const LOCAL_HOST_ALIASES = new Set(['localhost', '127.0.0.1', '0.0.0.0', '[::1]'])

function normalizeHost(value) {
  return String(value || '').trim().toLowerCase()
}

function normalizePort(value) {
  return String(value || '').trim()
}

function uniqueHosts(hosts) {
  const seen = new Set()
  return hosts.filter((host) => {
    const normalized = normalizeHost(host)
    if (!normalized || seen.has(normalized)) {
      return false
    }

    seen.add(normalized)
    return true
  })
}

export function getRuntimeHost(defaultHost = 'localhost') {
  if (typeof window === 'undefined') {
    return defaultHost
  }

  return normalizeHost(window.location.hostname) || defaultHost
}

export function getRuntimePort(defaultPort = DEFAULT_FRONTEND_PORT) {
  if (typeof window === 'undefined') {
    return defaultPort
  }

  return normalizePort(window.location.port) || defaultPort
}

export function isLocalAliasHost(host) {
  const normalizedHost = normalizeHost(host)
  return normalizedHost === PROJECTPUENTE_LOCAL_HOST || LOCAL_HOST_ALIASES.has(normalizedHost)
}

export function buildBrowserUrl({
  host,
  port = getRuntimePort(),
  protocol,
  pathname,
  search,
  hash,
} = {}) {
  const resolvedProtocol = protocol || (typeof window !== 'undefined' ? window.location.protocol : 'http:')
  const resolvedPathname = pathname ?? (typeof window !== 'undefined' ? window.location.pathname : '/')
  const resolvedSearch = search ?? (typeof window !== 'undefined' ? window.location.search : '')
  const resolvedHash = hash ?? (typeof window !== 'undefined' ? window.location.hash : '')

  const normalizedHost = normalizeHost(host) || 'localhost'
  const normalizedPort = normalizePort(port)
  const portSegment = normalizedPort ? `:${normalizedPort}` : ''

  return `${resolvedProtocol}//${normalizedHost}${portSegment}${resolvedPathname}${resolvedSearch}${resolvedHash}`
}

export function buildApiUrl(host, port = 8000) {
  return `http://${host}:${port}/api`
}

export function getApiHostCandidates(runtimeHost = getRuntimeHost(), { preferProjectAlias = true } = {}) {
  const normalizedHost = normalizeHost(runtimeHost)
  const hostCandidates = []

  if (LOCAL_HOST_ALIASES.has(normalizedHost)) {
    if (preferProjectAlias) {
      hostCandidates.push(PROJECTPUENTE_LOCAL_HOST)
      hostCandidates.push(normalizedHost)
    } else {
      hostCandidates.push(normalizedHost)
      hostCandidates.push(PROJECTPUENTE_LOCAL_HOST)
    }

    return uniqueHosts(hostCandidates)
  }

  hostCandidates.push(normalizedHost)

  if (normalizedHost === PROJECTPUENTE_LOCAL_HOST) {
    hostCandidates.push('localhost')
  }

  return uniqueHosts(hostCandidates)
}

export function getPreferredApiUrl(runtimeHost = getRuntimeHost(), options = {}) {
  const [preferredHost] = getApiHostCandidates(runtimeHost, options)
  return buildApiUrl(preferredHost || 'localhost')
}

async function probeHostReachability({
  host,
  port = getRuntimePort(),
  timeoutMs = 700,
  signal,
} = {}) {
  if (typeof window === 'undefined') {
    return false
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const abortFromParent = () => controller.abort()
  if (signal) {
    signal.addEventListener('abort', abortFromParent, { once: true })
  }

  try {
    const probeUrl = buildBrowserUrl({
      host,
      port,
      pathname: '/',
      search: '',
      hash: '',
    })

    await fetch(probeUrl, {
      method: 'GET',
      cache: 'no-store',
      mode: 'no-cors',
      signal: controller.signal,
    })

    return true
  } catch {
    return false
  } finally {
    clearTimeout(timeoutId)
    if (signal) {
      signal.removeEventListener('abort', abortFromParent)
    }
  }
}

export function shouldAttemptLocalAliasPromotion(runtimeHost = getRuntimeHost()) {
  const normalizedHost = normalizeHost(runtimeHost)
  return LOCAL_HOST_ALIASES.has(normalizedHost)
}

export async function canPromoteToProjectLocalHost({
  runtimeHost = getRuntimeHost(),
  runtimePort = getRuntimePort(),
  timeoutMs = 700,
  signal,
} = {}) {
  if (!shouldAttemptLocalAliasPromotion(runtimeHost)) {
    return false
  }

  return probeHostReachability({
    host: PROJECTPUENTE_LOCAL_HOST,
    port: runtimePort,
    timeoutMs,
    signal,
  })
}

async function probeApiHealth(apiUrl, timeoutMs, signal) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const abortFromParent = () => controller.abort()
  if (signal) {
    signal.addEventListener('abort', abortFromParent, { once: true })
  }

  try {
    const response = await fetch(`${apiUrl}/health/`, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    })

    return response.ok
  } catch {
    return false
  } finally {
    clearTimeout(timeoutId)
    if (signal) {
      signal.removeEventListener('abort', abortFromParent)
    }
  }
}

export async function resolveReachableApiUrl({
  runtimeHost = getRuntimeHost(),
  timeoutMs = 1200,
  preferProjectAlias = true,
  signal,
} = {}) {
  const hostCandidates = getApiHostCandidates(runtimeHost, { preferProjectAlias })

  for (let index = 0; index < hostCandidates.length; index += 1) {
    const host = hostCandidates[index]
    const apiUrl = buildApiUrl(host)
    const reachable = await probeApiHealth(apiUrl, timeoutMs, signal)

    if (reachable) {
      return {
        apiUrl,
        host,
        fallbackUsed: index > 0,
      }
    }
  }

  const fallbackHost = hostCandidates[0] || runtimeHost || 'localhost'
  return {
    apiUrl: buildApiUrl(fallbackHost),
    host: fallbackHost,
    fallbackUsed: false,
  }
}

export { PROJECTPUENTE_LOCAL_HOST }
