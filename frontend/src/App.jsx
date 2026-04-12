/**
 * App.jsx — Enterprise shell for the PUENTE dashboard.
 *
 * Architectural notes:
 * - Desktop layout uses a margin-coupled content column that tracks sidebar width (`ml-64 -> ml-24`).
 * - Mobile layout uses an off-canvas drawer + scrim, decoupled from desktop collapse behavior.
 * - Content container applies larger horizontal rhythm and max-width constraints for ultra-wide screens.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import './App.css'
import {
  applyThemeToDocument,
  loadSettings,
  SETTINGS_STORAGE_KEY,
  SETTINGS_UPDATED_EVENT,
} from './lib/settings'
import { isClientApiKeyConfigured, withApiKeyHeaders } from './lib/apiAuth'
import {
  buildBrowserUrl,
  canPromoteToProjectLocalHost,
  getPreferredApiUrl,
  getRuntimeHost,
  getRuntimePort,
  isLocalAliasHost,
  PROJECTPUENTE_LOCAL_HOST,
  resolveReachableApiUrl,
} from './lib/apiRuntime'
import ToastViewport from './components/feedback/ToastViewport'

// Enterprise layout components
import GlobalHeader from './components/layout/GlobalHeader'
import SidebarNav from './components/layout/SidebarNav'

// Screen components
import TranslateScreen from './components/screens/TranslateScreen'
import WikiVozScreen from './components/screens/WikiVozScreen'
import SettingsScreen from './components/screens/SettingsScreen'
import SystemEvaluationScreen from './components/screens/SystemEvaluationScreen'
import DatabaseAdminScreen from './components/screens/DatabaseAdminScreen'
import ActivityLogsScreen from './components/screens/ActivityLogsScreen'

const NAV_STATE_STORAGE_KEY = 'puente-nav-state-v1'
const NAV_SCREEN_ORDER = [
  'translate',
  'wiki-voz',
  'activity-logs',
  'evaluation',
  'db-admin',
  'settings',
]
const NAV_SCREEN_SET = new Set(NAV_SCREEN_ORDER)
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

const DEFAULT_TRANSLATION_META = {
  routeStrategy: 'direct',
  pivotLanguage: null,
  pivotUsed: false,
  model: '',
  isCached: false,
}

function normalizePathname(pathname) {
  const rawPath = String(pathname || '/').trim().toLowerCase()
  const withoutQueryHash = rawPath.split('?')[0].split('#')[0]
  const withLeadingSlash = withoutQueryHash.startsWith('/') ? withoutQueryHash : `/${withoutQueryHash}`
  const deduped = withLeadingSlash.replace(/\/{2,}/g, '/')

  if (deduped.length > 1 && deduped.endsWith('/')) {
    return deduped.slice(0, -1)
  }

  return deduped || '/'
}

function resolveScreenFromPath(pathname) {
  const normalizedPath = normalizePathname(pathname)

  if (normalizedPath === '/') {
    return 'translate'
  }

  return PATH_TO_SCREEN[normalizedPath] ?? null
}

function resolvePathFromScreen(screen) {
  return SCREEN_TO_PATH[screen] || SCREEN_TO_PATH.translate
}

function flattenValidationErrors(errors) {
  if (!errors || typeof errors !== 'object') {
    return ''
  }

  return Object.values(errors)
    .flat()
    .map((entry) => String(entry || '').trim())
    .filter(Boolean)
    .join(' ')
}

function extractApiErrorMessage(payload, fallback = 'Connection failed. Is the backend running?') {
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

function loadNavigationState() {
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

function App() {
  const initialSettings = loadSettings()
  const initialNavigationState = useMemo(() => loadNavigationState(), [])
  const clientApiKeyConfigured = isClientApiKeyConfigured()

  const [activeScreen, setActiveScreen] = useState(initialNavigationState.activeScreen)
  const [mountedScreens, setMountedScreens] = useState(() => ({
    [initialNavigationState.activeScreen]: true,
  }))
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(initialNavigationState.isSidebarCollapsed)
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false)
  const [isMobileViewport, setIsMobileViewport] = useState(
    typeof window === 'undefined' ? false : window.innerWidth < 768,
  )
  const [theme, setTheme] = useState(initialSettings.theme)
  const [pwaOnline, setPwaOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )
  const [latencyMs, setLatencyMs] = useState(null)
  const [apiUrl, setApiUrl] = useState(() => getPreferredApiUrl(getRuntimeHost()))
  const [toasts, setToasts] = useState([])

  // Translation state
  const [translatedText, setTranslatedText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [wikiData, setWikiData] = useState(null)
  const [translationMeta, setTranslationMeta] = useState(DEFAULT_TRANSLATION_META)

  // Health check state
  const [health, setHealth] = useState({
    checking: true,
    backendUp: false,
    nllbLoaded: false,
    loraAdapters: [],
    apiKeyRequired: false,
    ttsAvailable: false,
    ttsEngine: 'unavailable',
    engine: 'unknown',
  })

  const requestVersionRef = useRef(0)
  const abortRef = useRef(null)
  const toastTimersRef = useRef(new Map())

  useEffect(() => {
    setMountedScreens((previous) => {
      if (previous[activeScreen]) {
        return previous
      }

      return {
        ...previous,
        [activeScreen]: true,
      }
    })
  }, [activeScreen])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    // Keep the URL canonical even for root or legacy aliases.
    const canonicalPath = resolvePathFromScreen(activeScreen)
    const currentPath = normalizePathname(window.location.pathname)

    if (currentPath !== canonicalPath) {
      window.history.replaceState({}, '', canonicalPath)
    }
  }, [activeScreen])

  const dismissToast = useCallback((toastId) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== toastId))

    const timerId = toastTimersRef.current.get(toastId)
    if (timerId) {
      clearTimeout(timerId)
      toastTimersRef.current.delete(toastId)
    }
  }, [])

  const showToast = useCallback(({ title = '', message = '', variant = 'info', durationMs = 4200 }) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

    setToasts((previous) => ([
      ...previous.slice(-3),
      {
        id,
        title,
        message,
        variant,
        durationMs,
      },
    ]))

    const timerId = window.setTimeout(() => {
      dismissToast(id)
    }, durationMs)

    toastTimersRef.current.set(id, timerId)
  }, [dismissToast])

  useEffect(() => {
    const toastTimers = toastTimersRef.current

    return () => {
      toastTimers.forEach((timerId) => clearTimeout(timerId))
      toastTimers.clear()
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const runtimeHost = getRuntimeHost()
    const runtimePort = getRuntimePort()
    const controller = new AbortController()

    const resolveApiRoute = async () => {
      const runtimeUsesProjectAlias = runtimeHost === PROJECTPUENTE_LOCAL_HOST
      let preferProjectAlias = runtimeUsesProjectAlias

      if (!runtimeUsesProjectAlias && isLocalAliasHost(runtimeHost)) {
        const aliasReachable = await canPromoteToProjectLocalHost({
          runtimeHost,
          runtimePort,
          timeoutMs: 700,
          signal: controller.signal,
        })

        if (cancelled) {
          return
        }

        preferProjectAlias = aliasReachable

        if (aliasReachable) {
          const canonicalUrl = buildBrowserUrl({
            host: PROJECTPUENTE_LOCAL_HOST,
            port: runtimePort,
          })

          if (window.location.href !== canonicalUrl) {
            window.location.replace(canonicalUrl)
            return
          }
        }
      }

      const result = await resolveReachableApiUrl({
        runtimeHost,
        timeoutMs: preferProjectAlias ? 1200 : 650,
        preferProjectAlias,
        signal: controller.signal,
      })

      if (cancelled) {
        return
      }

      setApiUrl(result.apiUrl)

      if (runtimeUsesProjectAlias && result.host !== PROJECTPUENTE_LOCAL_HOST) {
        showToast({
          title: 'Using localhost fallback',
          message: 'projectpuente.local backend was not reachable. Verify hosts mapping and backend startup.',
          variant: 'warning',
          durationMs: 5200,
        })
      }
    }

    resolveApiRoute().catch(() => {
      if (cancelled) {
        return
      }

      setApiUrl(getPreferredApiUrl(runtimeHost, {
        preferProjectAlias: runtimeHost === PROJECTPUENTE_LOCAL_HOST,
      }))
    })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [showToast])

  const refreshHealth = useCallback(async () => {
    const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
    setHealth((prev) => ({ ...prev, checking: true }))

    try {
      const { data } = await axios.get(`${apiUrl}/health/`, { timeout: 10000 })
      const completedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
      setLatencyMs(Math.max(0, completedAt - startedAt))

      setHealth({
        checking: false,
        backendUp: true,
        nllbLoaded: Boolean(data.nllb_loaded),
        loraAdapters: data.lora_adapters || [],
        apiKeyRequired: Boolean(data.api_key_required),
        ttsAvailable: Boolean(data.tts_available),
        ttsEngine: data.tts_engine || 'unavailable',
        engine: data.engine || 'unknown',
        _lastChecked: Date.now(),
      })
    } catch {
      setLatencyMs(null)
      setHealth({
        checking: false,
        backendUp: false,
        nllbLoaded: false,
        loraAdapters: [],
        apiKeyRequired: false,
        ttsAvailable: false,
        ttsEngine: 'offline',
        engine: 'offline',
        _lastChecked: Date.now(),
      })
    }
  }, [apiUrl])

  useEffect(() => {
    refreshHealth()
    const interval = setInterval(refreshHealth, 30000)
    return () => clearInterval(interval)
  }, [refreshHealth])

  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [])

  useEffect(() => {
    applyThemeToDocument(theme)
  }, [theme])

  useEffect(() => {
    const handleOnline = () => setPwaOnline(true)
    const handleOffline = () => setPwaOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return

    const payload = {
      activeScreen,
      isSidebarCollapsed,
    }

    window.localStorage.setItem(NAV_STATE_STORAGE_KEY, JSON.stringify(payload))
  }, [activeScreen, isSidebarCollapsed])

  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsMobileSidebarOpen(false)
      }
    }

    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [])

  useEffect(() => {
    const handleResize = () => {
      const mobileViewport = window.innerWidth < 768
      setIsMobileViewport(mobileViewport)

      // Keep off-canvas state from lingering when crossing into desktop widths.
      if (!mobileViewport) {
        setIsMobileSidebarOpen(false)
      }
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const navigateToScreen = useCallback((screen, { historyMode = 'push' } = {}) => {
    const targetScreen = NAV_SCREEN_SET.has(screen) ? screen : 'translate'
    const targetPath = resolvePathFromScreen(targetScreen)

    setActiveScreen(targetScreen)
    setIsMobileSidebarOpen(false)

    if (typeof window === 'undefined') {
      return
    }

    const currentPath = normalizePathname(window.location.pathname)
    if (currentPath === targetPath) {
      return
    }

    // pushState updates the URL instantly while all screens stay mounted in the DOM.
    // We switch visibility with hidden/flex classes, so stateful views do not unmount.
    if (historyMode === 'replace') {
      window.history.replaceState({}, '', targetPath)
      return
    }

    window.history.pushState({}, '', targetPath)
  }, [])

  const handleNavigate = useCallback((screen) => {
    navigateToScreen(screen, { historyMode: 'push' })
  }, [navigateToScreen])

  useEffect(() => {
    const handlePopState = () => {
      const routeScreen = resolveScreenFromPath(window.location.pathname)

      if (!routeScreen) {
        navigateToScreen('translate', { historyMode: 'replace' })
        return
      }

      navigateToScreen(routeScreen, { historyMode: 'replace' })
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [navigateToScreen])

  useEffect(() => {
    const shortcutToScreen = {
      '1': NAV_SCREEN_ORDER[0],
      '2': NAV_SCREEN_ORDER[1],
      '3': NAV_SCREEN_ORDER[2],
      '4': NAV_SCREEN_ORDER[3],
      '5': NAV_SCREEN_ORDER[4],
      '6': NAV_SCREEN_ORDER[5],
    }

    const handleShortcut = (event) => {
      if (event.defaultPrevented) return

      const target = event.target
      const isEditable = target instanceof HTMLElement && (
        target.tagName === 'INPUT'
        || target.tagName === 'TEXTAREA'
        || target.tagName === 'SELECT'
        || target.isContentEditable
      )

      if (isEditable) {
        return
      }

      const key = event.key.toLowerCase()

      if ((event.ctrlKey || event.metaKey) && key === 'b') {
        event.preventDefault()
        setIsSidebarCollapsed((prev) => !prev)
        return
      }

      if ((event.ctrlKey || event.metaKey) && shortcutToScreen[key]) {
        event.preventDefault()
        navigateToScreen(shortcutToScreen[key], { historyMode: 'push' })
      }
    }

    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [navigateToScreen])

  useEffect(() => {
    const syncTheme = (nextSettings) => {
      if (!nextSettings?.theme) return
      if (nextSettings.theme !== theme) {
        setTheme(nextSettings.theme)
      }
    }

    const handleSettingsUpdated = (event) => {
      syncTheme(event?.detail ?? loadSettings())
    }

    const handleStorage = (event) => {
      if (event.key && event.key !== SETTINGS_STORAGE_KEY) return
      syncTheme(loadSettings())
    }

    window.addEventListener(SETTINGS_UPDATED_EVENT, handleSettingsUpdated)
    window.addEventListener('storage', handleStorage)

    return () => {
      window.removeEventListener(SETTINGS_UPDATED_EVENT, handleSettingsUpdated)
      window.removeEventListener('storage', handleStorage)
    }
  }, [theme])

  const handleTranslate = useCallback(async (payload, options = { trigger: 'manual' }) => {
    if (!payload?.text?.trim()) {
      return
    }

    if (health.apiKeyRequired && !clientApiKeyConfigured) {
      const message = 'Backend requires an API key. Set VITE_PUENTE_API_KEY in frontend/.env.'
      setError(message)
      showToast({
        title: 'API key required',
        message,
        variant: 'warning',
        durationMs: 5600,
      })
      setLoading(false)
      return
    }

    requestVersionRef.current += 1
    const requestVersion = requestVersionRef.current

    if (abortRef.current) {
      abortRef.current.abort()
    }
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError('')

    try {
      const response = await axios.post(`${apiUrl}/translate/`, payload, {
        headers: withApiKeyHeaders(),
        signal: controller.signal,
        timeout: 35000,
      })

      if (requestVersion !== requestVersionRef.current) {
        return
      }

      setTranslatedText(response.data.translated_text)
      setWikiData(response.data.wiki_voz ?? null)
      setTranslationMeta({
        routeStrategy: String(response.data.route_strategy || (response.data.pivot_used ? 'proximate-pivot' : 'direct')),
        pivotLanguage: response.data.pivot_language || null,
        pivotUsed: Boolean(response.data.pivot_used),
        model: String(response.data.model || ''),
        isCached: Boolean(response.data.is_cached),
      })

      // Keep status badges fresh if backend had recently been marked unavailable.
      if (!health.backendUp || !health.nllbLoaded) {
        refreshHealth()
      }
    } catch (err) {
      if (err?.code === 'ERR_CANCELED') {
        return
      }

      if (requestVersion !== requestVersionRef.current) {
        return
      }

      const message = extractApiErrorMessage(err.response?.data)
      setError(message)
      setTranslationMeta(DEFAULT_TRANSLATION_META)

      if (options.trigger === 'manual') {
        showToast({
          title: 'Translation failed',
          message,
          variant: 'error',
          durationMs: 5200,
        })
      }

      if (options.trigger === 'manual') {
        refreshHealth()
      }
    } finally {
      if (requestVersion === requestVersionRef.current) {
        setLoading(false)
      }
    }
  }, [apiUrl, clientApiKeyConfigured, health.apiKeyRequired, health.backendUp, health.nllbLoaded, refreshHealth, showToast])

  const toggleSidebarCollapse = () => {
    setIsSidebarCollapsed((prev) => !prev)
  }

  const toggleMobileSidebar = () => {
    setIsMobileSidebarOpen((prev) => !prev)
  }

  return (
    <div className="relative isolate flex min-h-screen bg-bg-dark text-text-primary transition-colors duration-300">
      {/* Ambient scene layers keep the shell visually alive without competing with content. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-28 left-[18%] h-72 w-72 rounded-full blur-3xl" style={{ backgroundColor: 'var(--a26-ambient-magenta)' }} />
        <div className="absolute right-[8%] top-16 h-64 w-64 rounded-full blur-3xl" style={{ backgroundColor: 'var(--a26-ambient-gold)' }} />
        <div className="a26-ambient-canvas absolute inset-0" />
      </div>

      {/* Scrim establishes depth hierarchy for mobile drawer and closes nav on outside click. */}
      {isMobileSidebarOpen ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-overlay-scrim/50 backdrop-blur-[2px] md:hidden"
          aria-label="Close navigation menu"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      ) : null}

      <SidebarNav
        activeScreen={activeScreen}
        onNavigate={handleNavigate}
        isCollapsed={isSidebarCollapsed}
        mobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
        isMobileViewport={isMobileViewport}
      />

      {/* Main column margin is coupled to desktop sidebar width with the same easing curve. */}
      <div
        className={`flex min-h-screen min-w-0 flex-1 flex-col transition-[margin] duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
          isSidebarCollapsed ? 'md:ml-24' : 'md:ml-64'
        }`}
      >
        <GlobalHeader
          activeScreen={activeScreen}
          pwaOnline={pwaOnline}
          backendUp={health.backendUp}
          latencyMs={latencyMs}
          checking={health.checking}
          onPing={refreshHealth}
          isSidebarCollapsed={isSidebarCollapsed}
          onToggleSidebarCollapse={toggleSidebarCollapse}
          onToggleMobileNav={toggleMobileSidebar}
          mobileNavOpen={isMobileSidebarOpen}
        />

        {/* Wide-screen readability is preserved by constraining content width and increasing horizontal breathing room. */}
        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5 lg:px-8 lg:py-6">
          <div className="mx-auto w-full max-w-7xl">
            <div
              className={`${activeScreen === 'translate' ? 'flex' : 'hidden'} min-h-[calc(100vh-8rem)] flex-col`}
              aria-hidden={activeScreen !== 'translate'}
            >
              <TranslateScreen
                onTranslate={handleTranslate}
                translatedText={translatedText}
                loading={loading}
                error={error}
                apiReady={health.backendUp && health.nllbLoaded && (!health.apiKeyRequired || clientApiKeyConfigured)}
                wikiData={wikiData}
                apiUrl={apiUrl}
                backendUp={health.backendUp}
                ttsAvailable={health.ttsAvailable}
                loraAdapters={health.loraAdapters}
                nllbLoaded={health.nllbLoaded}
                apiKeyRequired={health.apiKeyRequired}
                clientApiKeyConfigured={clientApiKeyConfigured}
                translationEngine={health.engine}
                translationMeta={translationMeta}
                notify={showToast}
              />
            </div>

            {mountedScreens['wiki-voz'] ? (
              <div
                className={`${activeScreen === 'wiki-voz' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
                aria-hidden={activeScreen !== 'wiki-voz'}
              >
                <WikiVozScreen
                  apiUrl={apiUrl}
                  backendUp={health.backendUp}
                  ttsAvailable={health.ttsAvailable}
                  notify={showToast}
                />
              </div>
            ) : null}

            {mountedScreens['activity-logs'] ? (
              <div
                className={`${activeScreen === 'activity-logs' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
                aria-hidden={activeScreen !== 'activity-logs'}
              >
                <ActivityLogsScreen apiUrl={apiUrl} backendUp={health.backendUp} notify={showToast} />
              </div>
            ) : null}

            {mountedScreens.evaluation ? (
              <div
                className={`${activeScreen === 'evaluation' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
                aria-hidden={activeScreen !== 'evaluation'}
              >
                <SystemEvaluationScreen />
              </div>
            ) : null}

            {mountedScreens['db-admin'] ? (
              <div
                className={`${activeScreen === 'db-admin' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
                aria-hidden={activeScreen !== 'db-admin'}
              >
                <DatabaseAdminScreen apiUrl={apiUrl} notify={showToast} />
              </div>
            ) : null}

            {mountedScreens.settings ? (
              <div
                className={`${activeScreen === 'settings' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
                aria-hidden={activeScreen !== 'settings'}
              >
                <SettingsScreen
                  health={health}
                  onRefreshHealth={refreshHealth}
                  activeTheme={theme}
                />
              </div>
            ) : null}
          </div>
        </main>
      </div>

      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default App
