/**
 * App.jsx — Main PUENTE application with responsive navigation
 * Integrates Header, BottomNav, and screen components
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import './App.css'

// Layout components
import Header from './components/layout/Header'
import BottomNav from './components/layout/BottomNav'

// Screen components
import TranslateScreen from './components/screens/TranslateScreen'
import WikiVozScreen from './components/screens/WikiVozScreen'
import SettingsScreen from './components/screens/SettingsScreen'

// Derive API URL from current hostname for LAN access
const API_URL = `http://${window.location.hostname}:8000/api`

function App() {
  // Navigation state — settings is an overlay, not a screen replacement
  const [activeScreen, setActiveScreen] = useState('translate')   // 'translate' | 'wiki-voz'
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Translation state
  const [translatedText, setTranslatedText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [wikiData, setWikiData] = useState(null)

  // Health check state
  const [health, setHealth] = useState({
    checking: true,
    backendUp: false,
    nllbLoaded: false,
    loraAdapters: [],
    apiKeyConfigured: false,
    ttsAvailable: false,
    ttsEngine: 'unavailable',
    engine: 'unknown',
  })

  const requestVersionRef = useRef(0)
  const abortRef = useRef(null)

  const refreshHealth = useCallback(async () => {
    setHealth((prev) => ({ ...prev, checking: true }))
    try {
      const { data } = await axios.get(`${API_URL}/health/`, { timeout: 10000 })
      setHealth({
        checking: false,
        backendUp: true,
        nllbLoaded: Boolean(data.nllb_loaded),
        loraAdapters: data.lora_adapters || [],
        apiKeyConfigured: Boolean(data.api_key_configured),
        ttsAvailable: Boolean(data.tts_available),
        ttsEngine: data.tts_engine || 'unavailable',
        engine: data.engine || 'unknown',
        _lastChecked: Date.now(),
      })
    } catch {
      setHealth({
        checking: false,
        backendUp: false,
        nllbLoaded: false,
        loraAdapters: [],
        apiKeyConfigured: false,
        ttsAvailable: false,
        ttsEngine: 'offline',
        engine: 'offline',
        _lastChecked: Date.now(),
      })
    }
  }, [])

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

  const handleTranslate = useCallback(async (payload, options = { trigger: 'manual' }) => {
    if (!payload?.text?.trim()) {
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
      const response = await axios.post(`${API_URL}/translate/`, payload, {
        signal: controller.signal,
        timeout: 35000,
      })

      if (requestVersion !== requestVersionRef.current) {
        return
      }

      setTranslatedText(response.data.translated_text)
      setWikiData(response.data.wiki_voz ?? null)

      // Refresh health on successful call to keep badge current.
      if (!health.backendUp || (!health.nllbLoaded && !health.apiKeyConfigured)) {
        refreshHealth()
      }
    } catch (err) {
      if (err?.code === 'ERR_CANCELED') {
        return
      }

      if (requestVersion !== requestVersionRef.current) {
        return
      }

      if (err.response?.data?.errors) {
        const msgs = Object.values(err.response.data.errors).flat().join(' ')
        setError(msgs)
      } else if (err.response?.data?.error) {
        setError(err.response.data.error)
      } else {
        setError('Connection failed. Is the backend running?')
      }

      if (options.trigger === 'manual') {
        refreshHealth()
      }
    } finally {
      if (requestVersion === requestVersionRef.current) {
        setLoading(false)
      }
    }
  }, [health.apiKeyConfigured, health.backendUp, refreshHealth])

  // Navigation handler — settings toggles an overlay panel
  const handleNavigate = (screen) => {
    if (screen === 'settings') {
      setSettingsOpen((prev) => !prev)
    } else {
      setActiveScreen(screen)
      setSettingsOpen(false)
    }
  }

  // Derive which nav item to highlight
  const visibleScreen = settingsOpen ? 'settings' : activeScreen

  // Render the active main screen (translate or wiki-voz)
  const renderMainScreen = () => {
    if (activeScreen === 'wiki-voz') {
      return (
        <WikiVozScreen
          apiUrl={API_URL}
          backendUp={health.backendUp}
          ttsAvailable={health.ttsAvailable}
        />
      )
    }

    return (
      <TranslateScreen
        onTranslate={handleTranslate}
        translatedText={translatedText}
        loading={loading}
        error={error}
        apiReady={health.backendUp && (health.nllbLoaded || health.apiKeyConfigured)}
        wikiData={wikiData}
        apiUrl={API_URL}
        backendUp={health.backendUp}
        ttsAvailable={health.ttsAvailable}
        loraAdapters={health.loraAdapters}
        nllbLoaded={health.nllbLoaded}
        translationEngine={health.engine}
      />
    )
  }

  return (
    <div className="min-h-screen bg-bg-dark text-text-primary flex flex-col">
      {/* Header */}
      <Header activeScreen={visibleScreen} onNavigate={handleNavigate} />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col pb-20 md:pb-0 relative">
        {/* Main screen — hidden on mobile when settings open, always visible on desktop */}
        <div className={`flex-1 flex flex-col ${settingsOpen ? 'hidden md:flex' : ''}`}>
          {renderMainScreen()}
        </div>

        {/* Mobile: Settings replaces content */}
        {settingsOpen && (
          <div className="flex-1 flex flex-col md:hidden">
            <SettingsScreen
              health={health}
              onRefreshHealth={refreshHealth}
              onClose={() => setSettingsOpen(false)}
            />
          </div>
        )}

        {/* Desktop: Settings side panel with backdrop */}
        {settingsOpen && (
          <div className="hidden md:block">
            {/* Dimmed backdrop */}
            <div
              className="fixed inset-0 top-16 bg-black/20 z-30"
              onClick={() => setSettingsOpen(false)}
            />
            {/* Slide-in panel */}
            <div className="fixed top-16 right-0 bottom-0 w-100 z-40 settings-panel">
              {/* Connection arrow pointing up toward Settings nav */}
              <div className="absolute -top-2 right-18 w-4 h-4 bg-bg-card border-t border-l border-border-subtle rotate-45 z-50" />
              <div className="h-full bg-bg-card border-l border-border-subtle shadow-2xl overflow-y-auto relative">
                <SettingsScreen
                  health={health}
                  onRefreshHealth={refreshHealth}
                  onClose={() => setSettingsOpen(false)}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Bottom Navigation (Mobile Only) */}
      <BottomNav activeScreen={visibleScreen} onNavigate={handleNavigate} />
    </div>
  )
}

export default App
