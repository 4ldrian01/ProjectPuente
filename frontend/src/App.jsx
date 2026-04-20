/**
 * App.jsx — Enterprise shell for the PUENTE dashboard.
 *
 * Architectural notes:
 * - Desktop layout uses a margin-coupled content column that tracks sidebar width (`ml-64 -> ml-20`).
 * - Mobile layout uses an off-canvas drawer + scrim, decoupled from desktop collapse behavior.
 * - Content container applies larger horizontal rhythm and max-width constraints for ultra-wide screens.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import './App.css'
import {
  applyThemeToDocument,
  loadSettings,
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
import { extractApiErrorMessage } from './lib/apiErrors'
import {
  NAV_SCREEN_ORDER,
  NAV_SCREEN_SET,
  NAV_STATE_STORAGE_KEY,
  loadNavigationState,
  normalizePathname,
  resolvePathFromScreen,
  resolveScreenFromPath,
} from './lib/appNavigation'
import { useSettingsSync } from './hooks/useSettingsSync'
import { useToastQueue } from './hooks/useToastQueue'
import { useBackendHealth } from './hooks/useBackendHealth'
import ToastViewport from './components/feedback/ToastViewport'

// Enterprise layout components
import GlobalHeader from './components/layout/GlobalHeader'
import SidebarNav from './components/layout/SidebarNav'
import AppScreenStack from './components/layout/AppScreenStack'

const DEFAULT_TRANSLATION_META = {
  routeStrategy: 'direct',
  pivotLanguage: null,
  pivotUsed: false,
  model: '',
  isCached: false,
}

function App() {
  const initialSettings = useMemo(() => loadSettings(), [])
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
  const [apiUrl, setApiUrl] = useState(() => getPreferredApiUrl(getRuntimeHost()))

  // Translation state
  const [translatedText, setTranslatedText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [wikiData, setWikiData] = useState(null)
  const [translationMeta, setTranslationMeta] = useState(DEFAULT_TRANSLATION_META)
  const { toasts, showToast, dismissToast } = useToastQueue()
  const { health, latencyMs, refreshHealth } = useBackendHealth(apiUrl)

  const requestVersionRef = useRef(0)
  const abortRef = useRef(null)

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

  const handleThemeSync = useCallback((nextSettings) => {
    const nextTheme = nextSettings?.theme
    if (!nextTheme) {
      return
    }

    setTheme((previousTheme) => (
      previousTheme === nextTheme ? previousTheme : nextTheme
    ))
  }, [])

  useSettingsSync(handleThemeSync)

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

      const message = extractApiErrorMessage(err.response?.data, 'Connection failed. Is the backend running?')
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
        <div className="a26-ambient-ribbons absolute inset-[8%_-12%_-20%_-12%]" />
        <div className="absolute -top-28 left-[18%] h-72 w-72 rounded-full blur-3xl" style={{ backgroundColor: 'var(--a26-ambient-magenta)' }} />
        <div className="absolute right-[8%] top-16 h-64 w-64 rounded-full blur-3xl" style={{ backgroundColor: 'var(--a26-ambient-gold)' }} />
        <div className="absolute -bottom-20 left-[44%] h-64 w-64 rounded-full blur-3xl" style={{ backgroundColor: 'var(--a26-ambient-indigo)' }} />
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
          isSidebarCollapsed ? 'md:ml-20' : 'md:ml-64'
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
          <AppScreenStack
            activeScreen={activeScreen}
            mountedScreens={mountedScreens}
            onTranslate={handleTranslate}
            translatedText={translatedText}
            loading={loading}
            error={error}
            wikiData={wikiData}
            apiUrl={apiUrl}
            health={health}
            clientApiKeyConfigured={clientApiKeyConfigured}
            translationMeta={translationMeta}
            theme={theme}
            onRefreshHealth={refreshHealth}
            notify={showToast}
          />
        </main>
      </div>

      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </div>
  )
}

export default App
