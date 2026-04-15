/**
 * settings.js — Frontend settings domain utilities.
 * Summary: Sanitizes persisted preferences, emits sync events, and applies theme mode to the document root.
 */

export const SETTINGS_STORAGE_KEY = 'puente_settings'
export const SETTINGS_UPDATED_EVENT = 'puente-settings-updated'

export const SOURCE_LANGUAGE_CODES = ['auto', 'en', 'tl', 'cbk', 'ceb', 'hil', 'es']
export const TARGET_LANGUAGE_CODES = ['cbk', 'ceb', 'hil', 'es', 'en', 'tl']
export const THEME_OPTIONS = ['dark', 'light']
export const DEFAULT_THEME = 'dark'

export const DEFAULT_SETTINGS = {
  defaultSourceLang: 'auto',
  defaultTargetLang: 'cbk',
  theme: DEFAULT_THEME,
}

export function sanitizeSettings(raw = {}) {
  const requestedSource = raw?.defaultSourceLang
  const requestedTarget = raw?.defaultTargetLang
  const requestedTheme = raw?.theme

  let defaultSourceLang = DEFAULT_SETTINGS.defaultSourceLang
  let defaultTargetLang = DEFAULT_SETTINGS.defaultTargetLang
  let theme = DEFAULT_SETTINGS.theme

  if (SOURCE_LANGUAGE_CODES.includes(requestedSource)) {
    defaultSourceLang = requestedSource
  }

  if (TARGET_LANGUAGE_CODES.includes(requestedTarget)) {
    defaultTargetLang = requestedTarget
  }

  if (defaultSourceLang !== 'auto' && defaultSourceLang === defaultTargetLang) {
    defaultTargetLang = TARGET_LANGUAGE_CODES.find((code) => code !== defaultSourceLang)
      || DEFAULT_SETTINGS.defaultTargetLang
  }

  if (THEME_OPTIONS.includes(requestedTheme)) {
    theme = requestedTheme
  }

  return { defaultSourceLang, defaultTargetLang, theme }
}

export function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY)
    if (!raw) return DEFAULT_SETTINGS
    return sanitizeSettings(JSON.parse(raw))
  } catch {
    return DEFAULT_SETTINGS
  }
}

export function saveSettings(nextSettings) {
  const sanitized = sanitizeSettings(nextSettings)

  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(sanitized))
    window.dispatchEvent(new CustomEvent(SETTINGS_UPDATED_EVENT, { detail: sanitized }))
  } catch {
    // Ignore storage failures; the UI still holds the current in-memory state.
  }

  return sanitized
}

export function applyThemeToDocument(theme) {
  const resolvedTheme = THEME_OPTIONS.includes(theme) ? theme : DEFAULT_THEME

  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', resolvedTheme)

    if (document.body) {
      document.body.setAttribute('data-theme', resolvedTheme)
    }

    document.documentElement.classList.toggle('dark', resolvedTheme === 'dark')
    document.documentElement.classList.toggle('light', resolvedTheme === 'light')

    const themeMeta = document.querySelector('meta[name="theme-color"]')
    if (themeMeta) {
      themeMeta.setAttribute('content', resolvedTheme === 'dark' ? '#121212' : '#f4f6fb')
    }
  }

  return resolvedTheme
}
