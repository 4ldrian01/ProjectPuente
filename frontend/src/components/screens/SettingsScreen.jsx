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
  TARGET_LANGUAGE_CODES,
} from '../../lib/settings'

const SOURCE_OPTIONS = [
  { value: 'auto', label: 'Auto-Detect' },
  { value: 'en', label: 'English' },
  { value: 'tl', label: 'Tagalog' },
  { value: 'cbk', label: 'Chavacano' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
].filter((option) => SOURCE_LANGUAGE_CODES.includes(option.value))

const TARGET_OPTIONS = [
  { value: 'cbk', label: 'Chavacano' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
  { value: 'en', label: 'English' },
  { value: 'tl', label: 'Tagalog' },
].filter((option) => TARGET_LANGUAGE_CODES.includes(option.value))

function timeAgo(ts) {
  if (!ts) return 'never'
  const diff = Math.round((Date.now() - ts) / 1000)
  if (diff < 5) return 'just now'
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export default function SettingsScreen({ health, onRefreshHealth, onClose }) {
  const saved = loadSettings()
  const [defaultSourceLang, setDefaultSourceLang] = useState(saved?.defaultSourceLang ?? 'auto')
  const [defaultTargetLang, setDefaultTargetLang] = useState(saved?.defaultTargetLang ?? 'cbk')

  // Live "last checked" ticker — re-renders every 5 seconds
  const [, setTick] = useState(0)
  const tickRef = useRef(null)
  useEffect(() => {
    tickRef.current = setInterval(() => setTick((t) => t + 1), 5000)
    return () => clearInterval(tickRef.current)
  }, [])

  const commitSettings = (nextSettings) => {
    const sanitized = saveSettings(nextSettings)
    setDefaultSourceLang(sanitized.defaultSourceLang)
    setDefaultTargetLang(sanitized.defaultTargetLang)
  }

  const handleSourceChange = (value) => {
    commitSettings({ defaultSourceLang: value, defaultTargetLang })
  }

  const handleTargetChange = (value) => {
    commitSettings({ defaultSourceLang, defaultTargetLang: value })
  }

  const lastChecked = health?._lastChecked

  return (
    <div className="flex-1 px-4 sm:px-6 py-4 md:py-6 w-full overflow-y-auto">
      {/* Header with close button */}
      <div className="flex items-center justify-between mb-6">
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
      <section className="mb-8">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Translation Preferences</h3>
        
        <div className="space-y-4">
          {/* Default Source Language */}
          <div className="bg-bg-card border border-border-subtle rounded-xl p-4">
            <p className="font-medium text-text-primary mb-2">Default Source Language</p>
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
          <div className="bg-bg-card border border-border-subtle rounded-xl p-4">
            <p className="font-medium text-text-primary mb-2">Default Target Language</p>
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
      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text-primary">Connection Status</h3>
          <span className="text-xs text-text-secondary">
            {health?.checking ? 'Checking…' : `Updated ${timeAgo(lastChecked)}`}
          </span>
        </div>
        
        <div className="bg-bg-card border border-border-subtle rounded-xl p-4 space-y-3">
          {/* Backend Status */}
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Backend Server</span>
            <span className={`flex items-center gap-2 text-sm font-medium ${
              health?.backendUp ? 'text-emerald-400' : 'text-red-400'
            }`}>
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                health?.backendUp ? 'bg-emerald-400' : 'bg-red-400'
              }`} />
              {health?.backendUp ? 'Online' : 'Offline'}
            </span>
          </div>

          {/* NLLB-200 Model Status */}
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">NLLB-200 Model</span>
            <span className={`flex items-center gap-2 text-sm font-medium ${
              health?.nllbLoaded ? 'text-emerald-400' : 'text-amber-400'
            }`}>
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                health?.nllbLoaded ? 'bg-emerald-400' : 'bg-amber-400'
              }`} />
              {health?.nllbLoaded ? 'Loaded' : 'Not Loaded'}
            </span>
          </div>

          {/* LoRA Adapters */}
          {health?.loraAdapters && health.loraAdapters.length > 0 && (
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">LoRA Adapters</span>
              <span className="text-sm font-medium text-emerald-400">
                {health.loraAdapters.join(', ')}
              </span>
            </div>
          )}

          {/* Engine */}
          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Translation Engine</span>
            <span className="text-sm font-medium text-text-primary capitalize">
              {health?.engine || 'Unknown'}
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-text-secondary">Speech Engine</span>
            <span className={`text-sm font-medium ${health?.ttsAvailable ? 'text-emerald-400' : 'text-amber-400'}`}>
              {health?.ttsAvailable ? (health?.ttsEngine || 'edge-tts') : 'Unavailable'}
            </span>
          </div>

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

      {/* About Section */}
      <section>
        <h3 className="text-lg font-semibold text-text-primary mb-4">About</h3>
        
        <div className="bg-bg-card border border-border-subtle rounded-xl p-4 space-y-3">
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
