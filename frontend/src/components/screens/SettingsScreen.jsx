/**
 * SettingsScreen.jsx — App settings and configuration
 * Renders as a side-panel on desktop, full-screen on mobile.
 *
 * Features: Default language preferences, live Connection Status,
 * NLLB model status, about section.
 * Auto-Translate and TTS are always-on (no toggles needed).
 * All preferences are persisted to localStorage.
 */

import { useState, useEffect, useRef } from 'react'
import { CloseIcon } from '../icons/NavIcons'
import { WIKI_VOZ_ENTRY_GOAL, WIKI_VOZ_ENTRIES } from '../../data/wikiVozData'
import {
  loadSettings,
  saveSettings,
  SOURCE_LANGUAGE_CODES,
  SETTINGS_STORAGE_KEY,
  SETTINGS_UPDATED_EVENT,
  TARGET_LANGUAGE_CODES,
  THEME_OPTIONS,
} from '../../lib/settings'
import { isClientApiKeyConfigured } from '../../lib/apiAuth'

const SOURCE_OPTIONS = [
  { value: 'auto', label: 'Auto-Detect' },
  { value: 'en', label: 'English' },
  { value: 'tl', label: 'Tagalog' },
  { value: 'cbk', label: 'Chavacano' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'es', label: 'Spanish' },
].filter((option) => SOURCE_LANGUAGE_CODES.includes(option.value))

const TARGET_OPTIONS = [
  { value: 'cbk', label: 'Chavacano' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'es', label: 'Spanish' },
  { value: 'en', label: 'English' },
  { value: 'tl', label: 'Tagalog' },
].filter((option) => TARGET_LANGUAGE_CODES.includes(option.value))

const TELEMETRY_API_URL = `http://${window.location.hostname}:8000/api/telemetry/`
const TELEMETRY_POLL_INTERVAL_MS = 4000
const FALLBACK_GPU_TOTAL_GB = 4.0
const FALLBACK_SYSTEM_RAM_TOTAL_GB = 8.0

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function timeAgo(ts) {
  if (!ts) return 'never'
  const diff = Math.round((Date.now() - ts) / 1000)
  if (diff < 5) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function SettingsScreen({ health, onRefreshHealth, onClose, activeTheme = 'dark' }) {
  const clientApiKeyConfigured = isClientApiKeyConfigured()
  const saved = loadSettings()
  const [defaultSourceLang, setDefaultSourceLang] = useState(saved?.defaultSourceLang ?? 'auto')
  const [defaultTargetLang, setDefaultTargetLang] = useState(saved?.defaultTargetLang ?? 'cbk')
  const [theme, setTheme] = useState(saved?.theme ?? activeTheme)
  const [telemetry, setTelemetry] = useState({
    loading: true,
    error: '',
    ramUsedGb: 0,
    ramTotalGb: FALLBACK_SYSTEM_RAM_TOTAL_GB,
    ramPercent: 0,
    gpuAvailable: false,
    gpuName: '',
    gpuUsedGb: 0,
    gpuTotalGb: FALLBACK_GPU_TOTAL_GB,
    gpuPercent: 0,
    gpuReason: '',
  })

  // Live "last checked" ticker — re-renders every 5 seconds
  const [, setTick] = useState(0)
  const tickRef = useRef(null)
  useEffect(() => {
    tickRef.current = setInterval(() => setTick((t) => t + 1), 5000)
    return () => clearInterval(tickRef.current)
  }, [])

  useEffect(() => {
    let disposed = false

    const pollTelemetry = async () => {
      try {
        const response = await fetch(TELEMETRY_API_URL, {
          method: 'GET',
          cache: 'no-store',
        })

        const payload = await response.json().catch(() => ({}))

        if (!response.ok) {
          throw new Error(payload?.error || 'Telemetry endpoint unavailable.')
        }

        if (disposed) return

        const ram = payload?.ram || {}
        const gpu = payload?.gpu || {}

        setTelemetry({
          loading: false,
          error: '',
          ramUsedGb: Number(ram.used_gb ?? 0),
          ramTotalGb: Number(ram.total_gb ?? FALLBACK_SYSTEM_RAM_TOTAL_GB),
          ramPercent: Number(ram.percent ?? 0),
          gpuAvailable: Boolean(gpu.available),
          gpuName: String(gpu.name || ''),
          gpuUsedGb: Number(gpu.used_gb ?? 0),
          gpuTotalGb: Number(gpu.total_gb ?? FALLBACK_GPU_TOTAL_GB),
          gpuPercent: Number(gpu.percent ?? 0),
          gpuReason: String(gpu.reason || ''),
        })
      } catch (err) {
        if (disposed) return

        setTelemetry((previous) => ({
          ...previous,
          loading: false,
          error: err?.message || 'Unable to load hardware telemetry.',
        }))
      }
    }

    pollTelemetry()
    const timer = setInterval(pollTelemetry, TELEMETRY_POLL_INTERVAL_MS)

    return () => {
      disposed = true
      clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (THEME_OPTIONS.includes(activeTheme) && activeTheme !== theme) {
      setTheme(activeTheme)
    }
  }, [activeTheme, theme])

  useEffect(() => {
    const applyIncomingSettings = (nextSettings) => {
      if (!nextSettings) return

      setDefaultSourceLang(nextSettings.defaultSourceLang)
      setDefaultTargetLang(nextSettings.defaultTargetLang)
      setTheme(nextSettings.theme)
    }

    const handleSettingsUpdated = (event) => {
      applyIncomingSettings(event?.detail ?? loadSettings())
    }

    const handleStorage = (event) => {
      if (event.key && event.key !== SETTINGS_STORAGE_KEY) return
      applyIncomingSettings(loadSettings())
    }

    window.addEventListener(SETTINGS_UPDATED_EVENT, handleSettingsUpdated)
    window.addEventListener('storage', handleStorage)

    return () => {
      window.removeEventListener(SETTINGS_UPDATED_EVENT, handleSettingsUpdated)
      window.removeEventListener('storage', handleStorage)
    }
  }, [])

  const commitSettings = (nextSettings) => {
    const sanitized = saveSettings({
      defaultSourceLang,
      defaultTargetLang,
      theme,
      ...nextSettings,
    })
    setDefaultSourceLang(sanitized.defaultSourceLang)
    setDefaultTargetLang(sanitized.defaultTargetLang)
    setTheme(sanitized.theme)
  }

  const handleSourceChange = (value) => {
    commitSettings({ defaultSourceLang: value, defaultTargetLang })
  }

  const handleTargetChange = (value) => {
    commitSettings({ defaultSourceLang, defaultTargetLang: value })
  }

  const handleThemeToggle = () => {
    commitSettings({ theme: theme === 'dark' ? 'light' : 'dark' })
  }

  const lastChecked = health?._lastChecked
  const gpuTotalGb = telemetry.gpuTotalGb > 0 ? telemetry.gpuTotalGb : FALLBACK_GPU_TOTAL_GB
  const ramTotalGb = telemetry.ramTotalGb > 0 ? telemetry.ramTotalGb : FALLBACK_SYSTEM_RAM_TOTAL_GB
  const gpuPercent = clamp(telemetry.gpuPercent, 0, 100)
  const ramPercent = clamp(telemetry.ramPercent, 0, 100)

  return (
    <div className="flex-1 px-4 sm:px-6 py-4 md:py-5 w-full overflow-y-auto">
      {/* Header with close button */}
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-text-primary">Settings</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors"
            aria-label="Close settings"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Translation Preferences */}
      <section className="mb-6">
        <h3 className="mb-3 text-lg font-semibold text-text-primary">Appearance</h3>

        <div className="rounded-xl border border-border-subtle bg-bg-card p-3.5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-text-primary">Theme</p>
              <p className="mt-0.5 text-xs text-text-secondary">
                Switch between the default dark mode and a full light mode across the app.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className={`text-xs font-semibold ${theme === 'light' ? 'text-accent-gold' : 'text-text-secondary'}`}>
                Light
              </span>
              <button
                onClick={handleThemeToggle}
                className={`toggle-switch ${theme === 'dark' ? 'active bg-accent-magenta' : 'bg-bg-elevated'}`}
                aria-label="Toggle theme"
                title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                <div className="toggle-knob" />
              </button>
              <span className={`text-xs font-semibold ${theme === 'dark' ? 'text-accent-magenta' : 'text-text-secondary'}`}>
                Dark
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Translation Preferences */}
      <section className="mb-6">
        <h3 className="mb-3 text-lg font-semibold text-text-primary">Translation Preferences</h3>
        
        <div className="space-y-3">
          {/* Default Source Language */}
          <div className="rounded-xl border border-border-subtle bg-bg-card p-3.5">
            <p className="mb-2 text-sm font-medium text-text-primary">Default Source Language</p>
            <select
              value={defaultSourceLang}
              onChange={(e) => handleSourceChange(e.target.value)}
              className="w-full bg-bg-elevated border border-border-subtle rounded-lg px-4 py-2.5 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-magenta"
            >
              {SOURCE_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Default Target Language */}
          <div className="rounded-xl border border-border-subtle bg-bg-card p-3.5">
            <p className="mb-2 text-sm font-medium text-text-primary">Default Target Language</p>
            <select
              value={defaultTargetLang}
              onChange={(e) => handleTargetChange(e.target.value)}
              className="w-full bg-bg-elevated border border-border-subtle rounded-lg px-4 py-2.5 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-magenta"
            >
              {TARGET_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <p className="px-1 text-xs text-text-secondary">
            These defaults update the translation module immediately and stay saved even after a hard refresh.
          </p>
        </div>
      </section>

      {/* Connection Status — Live Updating */}
      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-text-primary">Connection Status</h3>
          <span className="text-xs text-text-secondary">
            {health?.checking ? 'Checking…' : `Updated ${timeAgo(lastChecked)}`}
          </span>
        </div>
        
        <div className="rounded-xl border border-border-subtle bg-bg-card p-3.5 space-y-2.5">
          {/* Backend Status */}
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Backend Server</span>
            <span className={`flex items-center gap-2 text-sm font-medium ${
              health?.backendUp ? 'text-state-good' : 'text-state-bad'
            }`}>
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                health?.backendUp ? 'bg-state-good' : 'bg-state-bad'
              }`} />
              {health?.backendUp ? 'Online' : 'Offline'}
            </span>
          </div>

          {/* NLLB-200 Model Status */}
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Local NLLB-200 (8-bit)</span>
            <span className={`flex items-center gap-2 text-sm font-medium ${
              health?.nllbLoaded ? 'text-state-good' : 'text-state-warn'
            }`}>
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                health?.nllbLoaded ? 'bg-state-good' : 'bg-state-warn'
              }`} />
              {health?.nllbLoaded ? 'Loaded' : 'Not Loaded'}
            </span>
          </div>

          {/* LoRA Adapters */}
          {health?.loraAdapters && health.loraAdapters.length > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">LoRA Adapters</span>
              <span className="text-sm font-medium text-state-good">
                {health.loraAdapters.join(', ')}
              </span>
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Speech Engine</span>
            <span className={`text-sm font-medium ${health?.ttsAvailable ? 'text-state-good' : 'text-state-warn'}`}>
              {health?.ttsAvailable ? (health?.ttsEngine || 'edge-tts') : 'Unavailable'}
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Write Endpoint Auth</span>
            <span className={`text-sm font-medium ${health?.apiKeyRequired ? 'text-state-warn' : 'text-state-good'}`}>
              {health?.apiKeyRequired ? 'API key required' : 'Open (LAN mode)'}
            </span>
          </div>

          {health?.apiKeyRequired && (
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">Client API Key</span>
              <span className={`text-sm font-medium ${clientApiKeyConfigured ? 'text-state-good' : 'text-state-bad'}`}>
                {clientApiKeyConfigured ? 'Configured' : 'Missing'}
              </span>
            </div>
          )}

          {/* Refresh Button */}
          <button
            onClick={onRefreshHealth}
            disabled={health?.checking}
            className="w-full mt-3 bg-bg-elevated hover:bg-border-subtle disabled:opacity-50 text-text-primary font-medium py-2.5 px-4 rounded-lg transition-colors text-sm"
          >
            {health?.checking ? 'Checking…' : 'Refresh Now'}
          </button>
        </div>
      </section>

      {/* Hardware Telemetry */}
      <section className="mb-6">
        <h3 className="mb-3 text-lg font-semibold text-text-primary">Hardware Telemetry</h3>

        <div className="rounded-xl border border-border-subtle bg-bg-card p-3.5 space-y-3">
          {telemetry.loading && (
            <p className="text-xs text-text-secondary">Loading live telemetry…</p>
          )}

          {!telemetry.loading && telemetry.error && (
            <p className="text-xs text-status-danger-text">Telemetry error: {telemetry.error}</p>
          )}

          <div>
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className="text-text-secondary">GPU VRAM</span>
              <span className="font-medium text-text-primary">
                {telemetry.gpuAvailable ? `${telemetry.gpuUsedGb.toFixed(2)} GB / ${gpuTotalGb.toFixed(2)} GB` : 'Unavailable'}
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-bg-elevated overflow-hidden">
              <div
                className="h-full rounded-full bg-linear-to-r from-emerald-400 to-yellow-400 transition-all duration-500"
                style={{ width: `${gpuPercent}%` }}
              />
            </div>
            {telemetry.gpuAvailable && telemetry.gpuName && (
              <p className="mt-1 text-[11px] text-text-secondary">{telemetry.gpuName}</p>
            )}
            {!telemetry.gpuAvailable && telemetry.gpuReason && (
              <p className="mt-1 text-[11px] text-status-warning-text">GPU telemetry unavailable: {telemetry.gpuReason}</p>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className="text-text-secondary">System RAM</span>
              <span className="font-medium text-text-primary">{telemetry.ramUsedGb.toFixed(2)} GB / {ramTotalGb.toFixed(2)} GB</span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-bg-elevated overflow-hidden">
              <div
                className="h-full rounded-full bg-linear-to-r from-yellow-400 to-red-500 transition-all duration-500"
                style={{ width: `${ramPercent}%` }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section>
        <h3 className="mb-3 text-lg font-semibold text-text-primary">About</h3>
        
        <div className="rounded-xl border border-border-subtle bg-bg-card p-3.5 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Version</span>
            <span className="text-sm font-medium text-text-primary">1.0.0</span>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Wiki-Voz Entries</span>
            <span className="text-sm font-medium text-text-primary">
              {WIKI_VOZ_ENTRIES.length} / {WIKI_VOZ_ENTRY_GOAL.futureTargetTotal}+ starter cards
            </span>
          </div>

          <p className="text-xs text-text-secondary pt-2 border-t border-border-subtle">
            PUENTE is an offline-first neural machine translation system powered by 
            NLLB-200 with LoRA adapters, designed to preserve cultural nuances 
            in Philippine languages with Wiki-Voz integration for real-time cultural context.
          </p>
        </div>
      </section>
    </div>
  )
}
