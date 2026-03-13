export const SETTINGS_STORAGE_KEY = 'puente_settings'
export const SETTINGS_UPDATED_EVENT = 'puente-settings-updated'

export const SOURCE_LANGUAGE_CODES = ['auto', 'en', 'tl', 'cbk', 'hil', 'ceb']
export const TARGET_LANGUAGE_CODES = ['cbk', 'hil', 'ceb', 'en', 'tl']

export const DEFAULT_SETTINGS = {
  defaultSourceLang: 'auto',
  defaultTargetLang: 'cbk',
}

export function sanitizeSettings(raw = {}) {
  const requestedSource = raw?.defaultSourceLang
  const requestedTarget = raw?.defaultTargetLang

  let defaultSourceLang = DEFAULT_SETTINGS.defaultSourceLang
  let defaultTargetLang = DEFAULT_SETTINGS.defaultTargetLang

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

  return { defaultSourceLang, defaultTargetLang }
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
