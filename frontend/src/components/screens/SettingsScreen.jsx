/**
 * SettingsScreen.jsx — Preferences and connection health only.
 *
 * Phase 4 God Mode split:
 * - Keeps user preferences (theme, default languages)
 * - Adds mock Max VRAM allocation slider
 * - Keeps connection status panel (Backend, NLLB-200, edge-tts)
 */

import { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2,
  Cpu,
  Gauge,
  KeyRound,
  RefreshCcw,
  Server,
  Sparkles,
  SunMoon,
} from 'lucide-react'
import { CloseIcon } from '../icons/NavIcons'
import {
  loadSettings,
  saveSettings,
  SOURCE_LANGUAGE_CODES,
  SETTINGS_STORAGE_KEY,
  SETTINGS_UPDATED_EVENT,
  TARGET_LANGUAGE_CODES,
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

const VRAM_PREF_STORAGE_KEY = 'puente_mock_max_vram_allocation'
const DEFAULT_VRAM_ALLOCATION = 70
const VRAM_FALLBACK_BUDGET_GB = 8

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function loadMockVramAllocation() {
  try {
    const raw = localStorage.getItem(VRAM_PREF_STORAGE_KEY)
    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) {
      return DEFAULT_VRAM_ALLOCATION
    }
    return clamp(Math.round(parsed), 10, 100)
  } catch {
    return DEFAULT_VRAM_ALLOCATION
  }
}

function saveMockVramAllocation(value) {
  const sanitized = clamp(Math.round(Number(value) || DEFAULT_VRAM_ALLOCATION), 10, 100)

  try {
    localStorage.setItem(VRAM_PREF_STORAGE_KEY, String(sanitized))
  } catch {
    // Ignore localStorage failures; slider still updates in-memory state.
  }

  return sanitized
}

function timeAgo(timestamp) {
  if (!timestamp) return 'never'

  const diffSec = Math.round((Date.now() - timestamp) / 1000)
  if (diffSec < 5) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  return `${Math.floor(diffSec / 3600)}h ago`
}

function ConnectionRow({ icon, label, value, healthy, hint }) {
  const IconGlyph = icon

  return (
    <div className="rounded-2xl border border-border-subtle/70 bg-bg-elevated/45 px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-2 text-sm text-text-secondary">
          <span className={`inline-flex h-7 w-7 items-center justify-center rounded-xl border ${healthy ? 'border-status-success-border/45 bg-status-success-bg/60 text-status-success-text' : 'border-status-warning-border/45 bg-status-warning-bg/65 text-status-warning-text'}`}>
            <IconGlyph className="h-[0.875rem] w-[0.875rem]" />
          </span>
          {label}
        </span>

        <span className={`inline-flex items-center gap-2 text-sm font-semibold ${healthy ? 'text-state-good' : 'text-state-warn'}`}>
          <span className={`h-2 w-2 rounded-full ${healthy ? 'bg-state-good' : 'bg-state-warn'}`} />
          {value}
        </span>
      </div>

      {hint ? (
        <p className="mt-1 pl-9 text-xs text-text-secondary/85">{hint}</p>
      ) : null}
    </div>
  )
}

export default function SettingsScreen({ health, onRefreshHealth, onClose, activeTheme = 'dark' }) {
  const clientApiKeyConfigured = isClientApiKeyConfigured()
  const saved = useMemo(() => loadSettings(), [])

  const [defaultSourceLang, setDefaultSourceLang] = useState(saved.defaultSourceLang)
  const [defaultTargetLang, setDefaultTargetLang] = useState(saved.defaultTargetLang)
  const [theme, setTheme] = useState(saved.theme || activeTheme)
  const [mockVramAllocation, setMockVramAllocation] = useState(loadMockVramAllocation())
  const [, setTick] = useState(0)

  useEffect(() => {
    const ticker = setInterval(() => setTick((previous) => previous + 1), 5000)
    return () => clearInterval(ticker)
  }, [])

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
      if (event.key === VRAM_PREF_STORAGE_KEY) {
        setMockVramAllocation(loadMockVramAllocation())
        return
      }

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

  const handleVramSliderChange = (event) => {
    const value = saveMockVramAllocation(event.target.value)
    setMockVramAllocation(value)
  }

  const handleApplyVramPreset = (value) => {
    const next = saveMockVramAllocation(value)
    setMockVramAllocation(next)
  }

  const handleResetDefaults = () => {
    commitSettings({
      defaultSourceLang: 'auto',
      defaultTargetLang: 'cbk',
      theme: activeTheme,
    })
    setMockVramAllocation(saveMockVramAllocation(DEFAULT_VRAM_ALLOCATION))
  }

  const estimatedVramCapGb = ((mockVramAllocation / 100) * VRAM_FALLBACK_BUDGET_GB).toFixed(2)
  const lastChecked = health?._lastChecked

  const connectionItems = [
    {
      key: 'backend',
      icon: Server,
      label: 'Backend API',
      value: health?.backendUp ? 'Online' : 'Offline',
      healthy: Boolean(health?.backendUp),
      hint: health?.backendUp ? 'HTTP service responding and reachable by frontend.' : 'No response from API health endpoint.',
    },
    {
      key: 'nllb',
      icon: Cpu,
      label: 'NLLB-200 Runtime',
      value: health?.nllbLoaded ? 'Loaded' : 'Not loaded',
      healthy: Boolean(health?.nllbLoaded),
      hint: health?.nllbLoaded ? 'Local translation model is mounted and available.' : 'Model unavailable, translation endpoints are limited.',
    },
    {
      key: 'tts',
      icon: Sparkles,
      label: 'Edge-TTS Engine',
      value: health?.ttsAvailable ? (health?.ttsEngine || 'Available') : 'Unavailable',
      healthy: Boolean(health?.ttsAvailable),
      hint: health?.ttsAvailable ? 'Speech synthesis channel is active.' : 'TTS channel is currently unavailable.',
    },
  ]

  if (health?.apiKeyRequired) {
    connectionItems.push({
      key: 'apikey',
      icon: KeyRound,
      label: 'Client API Key',
      value: clientApiKeyConfigured ? 'Configured' : 'Missing',
      healthy: clientApiKeyConfigured,
      hint: clientApiKeyConfigured ? 'Frontend key is aligned with backend requirement.' : 'Set VITE_PUENTE_API_KEY to enable write endpoints.',
    })
  }

  const healthyCount = connectionItems.filter((item) => item.healthy).length
  const healthScore = connectionItems.length > 0
    ? Math.round((healthyCount / connectionItems.length) * 100)
    : 0

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="a26-surface relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -left-10 top-4 h-32 w-32 rounded-full bg-accent-magenta/10 blur-3xl" />

        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="a26-subtitle">Settings and Health</p>
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Operator Preferences</h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-secondary">
              Personalized control layer for language defaults, visual theme, and runtime resource policy.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="a26-chip"><Gauge className="h-[0.875rem] w-[0.875rem]" /> Health {healthScore}%</span>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="a26-button-ghost inline-flex items-center justify-center p-2"
                aria-label="Close settings"
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.18fr_1fr]">
        <article className="a26-surface space-y-4 p-4 md:p-5">
          <h3 className="a26-subtitle">Preferences</h3>

          <div className="rounded-2xl border border-border-subtle/70 bg-bg-elevated/45 p-3.5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="inline-flex items-center gap-2 text-sm font-semibold text-text-primary">
                  <SunMoon className="h-4 w-4 text-accent-gold" />
                  Theme
                </p>
                <p className="mt-1 text-xs text-text-secondary">Switch dashboard palette across all screens.</p>
              </div>

              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold ${theme === 'light' ? 'text-accent-gold' : 'text-text-secondary'}`}>Light</span>
                <button
                  type="button"
                  onClick={handleThemeToggle}
                  className={`toggle-switch ${theme === 'dark' ? 'active bg-accent-magenta' : 'bg-bg-elevated'}`}
                  aria-label="Toggle theme"
                  role="switch"
                  aria-checked={theme === 'dark'}
                  title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                >
                  <div className="toggle-knob" />
                </button>
                <span className={`text-xs font-semibold ${theme === 'dark' ? 'text-accent-magenta' : 'text-text-secondary'}`}>Dark</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-border-subtle/70 bg-bg-elevated/45 p-3.5">
              <p className="mb-2 text-sm font-semibold text-text-primary">Default Source</p>
              <select
                value={defaultSourceLang}
                onChange={(event) => handleSourceChange(event.target.value)}
                className="w-full rounded-xl border border-border-subtle bg-bg-card px-3 py-2 text-sm text-text-primary focus:border-accent-magenta focus:outline-none"
              >
                {SOURCE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>

            <div className="rounded-2xl border border-border-subtle/70 bg-bg-elevated/45 p-3.5">
              <p className="mb-2 text-sm font-semibold text-text-primary">Default Target</p>
              <select
                value={defaultTargetLang}
                onChange={(event) => handleTargetChange(event.target.value)}
                className="w-full rounded-xl border border-border-subtle bg-bg-card px-3 py-2 text-sm text-text-primary focus:border-accent-magenta focus:outline-none"
              >
                {TARGET_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="rounded-2xl border border-border-subtle/70 bg-bg-elevated/45 p-3.5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="inline-flex items-center gap-2 text-sm font-semibold text-text-primary">
                  <Cpu className="h-4 w-4 text-accent-magenta" />
                  Max VRAM Allocation
                </p>
                <p className="mt-1 text-xs text-text-secondary">Mock resource governor for enterprise operator profiles.</p>
              </div>
              <span className="text-sm font-semibold text-accent-magenta">{mockVramAllocation}%</span>
            </div>

            <input
              type="range"
              min="10"
              max="100"
              step="1"
              value={mockVramAllocation}
              onChange={handleVramSliderChange}
              className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-lg bg-bg-card"
              aria-label="Max VRAM allocation"
            />

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {[55, 70, 85].map((preset) => (
                <button
                  type="button"
                  key={preset}
                  onClick={() => handleApplyVramPreset(preset)}
                  className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-all active:scale-[0.98] ${mockVramAllocation === preset ? 'border-accent-magenta/55 bg-accent-magenta/14 text-accent-magenta' : 'border-border-subtle/70 bg-bg-card text-text-secondary hover:text-text-primary'}`}
                >
                  {preset}% preset
                </button>
              ))}
            </div>

            <p className="mt-2 text-xs text-text-secondary">
              Target cap (mock): <span className="font-semibold text-text-primary">{estimatedVramCapGb} GB</span> of {VRAM_FALLBACK_BUDGET_GB.toFixed(2)} GB budget.
            </p>
          </div>

          <button
            type="button"
            onClick={handleResetDefaults}
            className="a26-button-ghost inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em]"
          >
            Reset Defaults
          </button>
        </article>

        <article className="a26-surface space-y-3 p-4 md:p-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="a26-subtitle">Connection Status</h3>
            <span className="text-xs text-text-secondary">
              {health?.checking ? 'Checking…' : `Updated ${timeAgo(lastChecked)}`}
            </span>
          </div>

          <div className="rounded-2xl border border-border-subtle/70 bg-bg-elevated/45 px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.14em] text-text-secondary">Operational Health</p>
            <div className="mt-1 flex items-end justify-between">
              <p className="text-3xl font-black text-text-primary">{healthScore}%</p>
              <span className={`inline-flex items-center gap-1 text-xs font-semibold ${healthScore >= 75 ? 'text-status-success-text' : 'text-status-warning-text'}`}>
                <CheckCircle2 className="h-[0.875rem] w-[0.875rem]" />
                {healthyCount}/{connectionItems.length} checks healthy
              </span>
            </div>
          </div>

          {connectionItems.map((item) => (
            <ConnectionRow
              key={item.key}
              icon={item.icon}
              label={item.label}
              value={item.value}
              healthy={item.healthy}
              hint={item.hint}
            />
          ))}

          <button
            type="button"
            onClick={onRefreshHealth}
            disabled={health?.checking}
            className="a26-button-primary mt-2 inline-flex w-full items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCcw className={`h-4 w-4 ${health?.checking ? 'animate-spin' : ''}`} />
            {health?.checking ? 'Checking…' : 'Refresh Status'}
          </button>
        </article>
      </section>
    </div>
  )
}
