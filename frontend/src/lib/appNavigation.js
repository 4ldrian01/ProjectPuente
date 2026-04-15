/**
 * appNavigation.js — Screen/path mapping and persisted nav state helpers.
 * Summary: Normalizes pathnames, resolves route aliases, and restores sidebar/screen state from storage.
 */

export const NAV_STATE_STORAGE_KEY = 'puente-nav-state-v1'

export const NAV_SCREEN_ORDER = [
  'translate',
  'wiki-voz',
  'activity-logs',
  'evaluation',
  'db-admin',
  'settings',
]

export const NAV_SCREEN_SET = new Set(NAV_SCREEN_ORDER)

const SCREEN_TO_PATH = {
  translate: '/translate',
  'wiki-voz': '/wiki-voz',
  'activity-logs': '/activity-logs',
  evaluation: '/evaluation',
  'db-admin': '/admin',
  settings: '/settings',
}

const PATH_TO_SCREEN = {
  '/translate': 'translate',
  '/wiki-voz': 'wiki-voz',
  '/activity-logs': 'activity-logs',
  '/evaluation': 'evaluation',
  '/admin': 'db-admin',
  '/db-admin': 'db-admin',
  '/settings': 'settings',
}

export function normalizePathname(pathname) {
  const rawPath = String(pathname || '/').trim().toLowerCase()
  const withoutQueryHash = rawPath.split('?')[0].split('#')[0]
  const withLeadingSlash = withoutQueryHash.startsWith('/') ? withoutQueryHash : `/${withoutQueryHash}`
  const deduped = withLeadingSlash.replace(/\/{2,}/g, '/')

  if (deduped.length > 1 && deduped.endsWith('/')) {
    return deduped.slice(0, -1)
  }

  return deduped || '/'
}

export function resolveScreenFromPath(pathname) {
  const normalizedPath = normalizePathname(pathname)

  if (normalizedPath === '/') {
    return 'translate'
  }

  return PATH_TO_SCREEN[normalizedPath] ?? null
}

export function resolvePathFromScreen(screen) {
  return SCREEN_TO_PATH[screen] || SCREEN_TO_PATH.translate
}

export function loadNavigationState() {
  const defaults = {
    activeScreen: 'translate',
    isSidebarCollapsed: false,
  }

  if (typeof window === 'undefined') {
    return defaults
  }

  try {
    const raw = window.localStorage.getItem(NAV_STATE_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    const pathScreen = resolveScreenFromPath(window.location.pathname)
    const activeScreen = pathScreen || defaults.activeScreen

    return {
      activeScreen,
      isSidebarCollapsed: Boolean(parsed?.isSidebarCollapsed),
    }
  } catch {
    return defaults
  }
}
