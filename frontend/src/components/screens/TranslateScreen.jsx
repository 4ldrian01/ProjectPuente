/**
 * TranslateScreen.jsx — Main translation screen (Google Translate-inspired).
 *
 * Desktop  → side-by-side input / output (2-col grid).
 * Mobile   → stacked, scrollable (1-col).
 *
 * Features: 5-language limit, mutual exclusion, swap, backend edge-tts,
 *           character counter (hidden when empty),
 *           formal/street toggle, cultural-term highlighting.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CopyIcon, SpeakerIcon } from '../icons/NavIcons'
import LanguageSelector from '../LanguageSelector'
import CulturalTermPopup from '../CulturalTermPopup'
import { CULTURAL_TERMS_MAP, getCulturalEntry } from '../../data/wikiVozData'
import { loadSettings, SETTINGS_STORAGE_KEY, SETTINGS_UPDATED_EVENT } from '../../lib/settings'
import { speakWithEdgeTts, stopEdgeTtsPlayback } from '../../lib/ttsClient'

/* ── Strict 5-language config ────────────────────────────────── */
const SOURCE_VISIBLE  = ['auto', 'en', 'tl']
const SOURCE_DROPDOWN = ['cbk', 'hil', 'ceb']
const TARGET_VISIBLE  = ['cbk', 'hil', 'ceb']
const TARGET_DROPDOWN = ['en', 'tl']

const LANGUAGE_LABELS = {
  auto: 'Auto-Detect',
  en: 'English',
  tl: 'Tagalog',
  cbk: 'Chavacano',
  hil: 'Hiligaynon',
  ceb: 'Cebuano/Bisaya',
}

/* ── Component ───────────────────────────────────────────────── */
export default function TranslateScreen({
  onTranslate,
  translatedText,
  loading,
  error,
  apiReady,
  wikiData,
  apiUrl,
  backendUp,
  ttsAvailable,
  loraAdapters = [],
  nllbLoaded = false,
  translationEngine = 'unknown',
}) {
  const initialSettings = useMemo(() => loadSettings(), [])

  const [sourceText, setSourceText]     = useState('')
  const [sourceLang, setSourceLang]     = useState(initialSettings.defaultSourceLang)
  const [targetLang, setTargetLang]     = useState(initialSettings.defaultTargetLang)
  const [isStreetMode, setIsStreetMode] = useState(false)
  const [selectedTerm, setSelectedTerm] = useState(null)
  const [copied, setCopied]             = useState(false)
  const [settingsNotice, setSettingsNotice] = useState('')
  const [ttsError, setTtsError]         = useState('')
  const [ttsLoadingKey, setTtsLoadingKey] = useState(null)

  const debounceMs      = 800
  const lastSentKeyRef  = useRef('')
  const forceRef        = useRef(false)
  const sourceTextareaRef = useRef(null)
  const copyResetTimerRef = useRef(null)

  const normalizedText = sourceText.trim()
  const canTranslate   = normalizedText.length > 0
  const hasTranslatedText = Boolean(translatedText?.trim())
  const activeMode = isStreetMode ? 'street' : 'formal'
  const activeModeLabel = isStreetMode ? 'Street' : 'Formal'

  /* Smooth auto-grow for input box (no jump) */
  useEffect(() => {
    const el = sourceTextareaRef.current
    if (!el) return
    const minHeight = 48
    el.style.height = 'auto'
    el.style.height = `${Math.max(minHeight, el.scrollHeight)}px`
  }, [sourceText])

  useEffect(() => {
    return () => {
      if (copyResetTimerRef.current) clearTimeout(copyResetTimerRef.current)
      stopEdgeTtsPlayback()
    }
  }, [])

  useEffect(() => {
    const applyIncomingSettings = (nextSettings) => {
      if (!nextSettings) return

      if (
        nextSettings.defaultSourceLang === sourceLang
        && nextSettings.defaultTargetLang === targetLang
      ) {
        return
      }

      setSourceLang(nextSettings.defaultSourceLang)
      setTargetLang(nextSettings.defaultTargetLang)
      setSettingsNotice(
        `Defaults updated: ${LANGUAGE_LABELS[nextSettings.defaultSourceLang]} → ${LANGUAGE_LABELS[nextSettings.defaultTargetLang]}.`,
      )
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
  }, [sourceLang, targetLang])

  useEffect(() => {
    if (!settingsNotice) return undefined

    const timer = setTimeout(() => setSettingsNotice(''), 2600)
    return () => clearTimeout(timer)
  }, [settingsNotice])

  useEffect(() => {
    setCopied(false)
  }, [translatedText])

  /* payload for the backend */
  const payload = useMemo(() => ({
    text: normalizedText,
    source_lang: sourceLang,
    target_lang: targetLang,
    mode: activeMode,
  }), [activeMode, normalizedText, sourceLang, targetLang])

  const payloadKey = useMemo(
    () => `${payload.text}||${payload.source_lang}||${payload.target_lang}||${payload.mode}`,
    [payload],
  )

  const sendTranslation = useCallback((trigger = 'auto') => {
    if (!canTranslate || !apiReady) return
    lastSentKeyRef.current = payloadKey
    onTranslate(payload, { trigger })
  }, [apiReady, canTranslate, onTranslate, payload, payloadKey])

  /* auto-translate (debounce or immediate when forced) */
  useEffect(() => {
    if (!apiReady || !canTranslate) return
    if (payloadKey === lastSentKeyRef.current) return

    if (forceRef.current) {
      forceRef.current = false
      sendTranslation('auto')
      return
    }

    const timer = setTimeout(() => sendTranslation('auto'), debounceMs)
    return () => clearTimeout(timer)
  }, [apiReady, canTranslate, payloadKey, sendTranslation])

  /* ── Language mutual-exclusion ── */
  const handleSourceChange = (code) => {
    setSourceLang(code)
    if (code !== 'auto' && code === targetLang) {
      const fallback = [...TARGET_VISIBLE, ...TARGET_DROPDOWN].find((c) => c !== code)
      if (fallback) setTargetLang(fallback)
    }
  }

  const handleTargetChange = (code) => {
    setTargetLang(code)
    if (sourceLang !== 'auto' && code === sourceLang) {
      const fallback = [...SOURCE_VISIBLE, ...SOURCE_DROPDOWN].find((c) => c !== 'auto' && c !== code)
      if (fallback) setSourceLang(fallback)
    }
  }

  /* ── Swap ── */
  const handleSwap = () => {
    if (sourceLang === 'auto') return
    const s = sourceLang, t = targetLang
    setSourceLang(t)
    setTargetLang(s)
    forceRef.current = true
  }

  const targetExclude = sourceLang === 'auto' ? null : sourceLang
  const sourceExclude = targetLang
  const effectiveSourceLang = sourceLang === 'auto' ? 'en' : sourceLang
  const canUseTts = backendUp && ttsAvailable

  const modeStatus = useMemo(() => {
    if (!backendUp) {
      return {
        className: 'border-amber-700/70 bg-amber-900/20 text-amber-200',
        message: `${activeModeLabel} mode is selected. It will apply automatically once the backend is reachable again.`,
      }
    }

    if (!nllbLoaded) {
      return {
        className: 'border-amber-700/70 bg-amber-900/20 text-amber-200',
        message: `${activeModeLabel} mode cannot run yet because the local NLLB model is not loaded.`,
      }
    }

    if (!loraAdapters.includes(activeMode)) {
      return {
        className: 'border-amber-700/70 bg-amber-900/20 text-amber-200',
        message: `${activeModeLabel} mode is available, but its LoRA adapter is not loaded yet. Using the base NLLB model, so the tone may sound more neutral than requested.`,
      }
    }

    return {
      className: 'border-emerald-700/60 bg-emerald-900/20 text-emerald-200',
      message: `${activeModeLabel} register is ready via the ${activeMode} LoRA adapter.`,
    }
  }, [activeMode, activeModeLabel, backendUp, loraAdapters, nllbLoaded])

  const effectiveError = useMemo(() => {
    if (!error) return ''

    const prefix = `${activeModeLabel} mode: `
    return error.startsWith(prefix) ? error : `${prefix}${error}`
  }, [activeModeLabel, error])

  const handleSpeak = useCallback(async (text, langCode, slot) => {
    if (!text?.trim() || !canUseTts) return

    setTtsError('')
    setTtsLoadingKey(slot)

    try {
      await speakWithEdgeTts({
        apiUrl,
        text,
        langCode,
      })
    } catch (err) {
      if (err?.code !== 'ERR_CANCELED') {
        setTtsError(err.message || 'Text-to-speech failed.')
      }
    } finally {
      setTtsLoadingKey((current) => (current === slot ? null : current))
    }
  }, [apiUrl, canUseTts])

  const handleCopyTranslation = useCallback(async () => {
    if (!translatedText?.trim() || !navigator?.clipboard) return
    try {
      await navigator.clipboard.writeText(translatedText)
      setCopied(true)
      if (copyResetTimerRef.current) clearTimeout(copyResetTimerRef.current)
      copyResetTimerRef.current = setTimeout(() => setCopied(false), 1400)
    } catch {
      setCopied(false)
    }
  }, [translatedText])

  /* ── Cultural-term highlighting ── */
  const renderHighlightedText = () => {
    if (!translatedText) return null
    return translatedText.split(/(\s+)/).map((word, i) => {
      const clean  = word.toLowerCase().replace(/[.,!?;:'"]/g, '')
      const termId = CULTURAL_TERMS_MAP[clean]
      if (termId) {
        return (
          <span
            key={i}
            className="cultural-term cursor-pointer text-accent-gold underline decoration-accent-gold decoration-2 underline-offset-2 hover:text-accent-gold/80 transition-colors"
            onClick={() => setSelectedTerm(getCulturalEntry(termId))}
          >{word}</span>
        )
      }
      return <span key={i}>{word}</span>
    })
  }

  /* ════════════════════════════════════════════════════════════
     Shared sub-elements
     ════════════════════════════════════════════════════════════ */

  const sourceLangBar = (
    <LanguageSelector
      selected={sourceLang}
      onSelect={handleSourceChange}
      visibleCodes={SOURCE_VISIBLE}
      dropdownCodes={SOURCE_DROPDOWN}
      excludeCode={sourceExclude}
    />
  )

  const targetLangBar = (
    <LanguageSelector
      selected={targetLang}
      onSelect={handleTargetChange}
      visibleCodes={TARGET_VISIBLE}
      dropdownCodes={TARGET_DROPDOWN}
      excludeCode={targetExclude}
    />
  )

  const swapBtn = (
    <button
      onClick={handleSwap}
      disabled={sourceLang === 'auto'}
      className="p-2 rounded-lg text-text-secondary hover:text-accent-magenta hover:bg-bg-elevated/60 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      title="Swap languages"
    >
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    </button>
  )

  const toggleSection = (
    <div className="flex items-center gap-3">
      <span className={`text-sm font-semibold transition-colors ${!isStreetMode ? 'text-accent-gold' : 'text-text-secondary'}`}>
        Formal
      </span>
      <button
        onClick={() => setIsStreetMode((v) => !v)}
        className={`toggle-switch ${isStreetMode ? 'active bg-accent-magenta' : 'bg-bg-elevated'}`}
        aria-label="Toggle translation mode"
      >
        <div className="toggle-knob" />
      </button>
      <span className={`text-sm font-semibold transition-colors ${isStreetMode ? 'text-accent-magenta' : 'text-text-secondary'}`}>
        Street
      </span>
    </div>
  )

  /* ── Input box (compact, Google Translate-style) ── */
  const renderInputBox = () => (
    <div className="bg-bg-card border border-zinc-600/90 rounded-xl flex flex-col min-h-16 md:min-h-22 focus-within:border-accent-magenta/90 transition-colors">
      <textarea
        ref={sourceTextareaRef}
        value={sourceText}
        onChange={(e) => setSourceText(e.target.value.slice(0, 250))}
        placeholder="Enter text to translate…"
        className="w-full bg-transparent text-text-primary text-base leading-relaxed placeholder-text-secondary/40 resize-none overflow-hidden focus:outline-none px-4 pt-3 pb-1 transition-[height] duration-150 ease-out"
        style={{ minHeight: '48px' }}
        maxLength={250}
      />
      <div className={`flex items-center px-4 py-1.5 border-t border-border-subtle/40 ${normalizedText ? 'justify-between' : 'justify-end'}`}>
        {normalizedText && (
          <button
            onClick={() => handleSpeak(sourceText, effectiveSourceLang, 'source')}
            disabled={!canUseTts}
            className="p-1.5 rounded-lg text-text-secondary hover:text-accent-magenta transition-colors disabled:opacity-30"
            aria-label="Listen to source text"
            title={canUseTts ? 'Listen to source text' : 'Backend Edge TTS is unavailable'}
          >
            <SpeakerIcon className={`w-4.5 h-4.5 ${ttsLoadingKey === 'source' ? 'animate-pulse' : ''}`} />
          </button>
        )}
        {/* Counter hidden when empty, visible on typing */}
        <span className={`text-xs tabular-nums transition-opacity duration-200 ${sourceText.length > 0 ? 'text-text-secondary opacity-100' : 'opacity-0'}`}>
          {sourceText.length}/250
        </span>
      </div>
    </div>
  )

  /* ── Output box (compact, Google Translate-style) ── */
  const renderOutputBox = () => (
    <div className="bg-bg-card/80 border border-border-subtle/25 rounded-xl flex flex-col min-h-16 md:min-h-22">
      <div className="flex-1 px-4 pt-3 pb-1">
        {loading ? (
          <div className="flex items-center gap-3 text-accent-magenta">
            <svg className="animate-spin h-4.5 w-4.5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Translating…</span>
          </div>
        ) : translatedText ? (
          <p className="text-text-primary text-base leading-relaxed wrap-break-word">{renderHighlightedText()}</p>
        ) : (
          <p className="text-text-secondary/40 italic text-base">Translation will appear here…</p>
        )}
        {effectiveError && (
          <div className="mt-2 bg-red-900/30 border border-red-800 text-red-300 rounded-lg px-3 py-1.5 text-sm">{effectiveError}</div>
        )}
        {ttsError && (
          <div className="mt-2 bg-amber-900/20 border border-amber-700/70 text-amber-200 rounded-lg px-3 py-1.5 text-sm">{ttsError}</div>
        )}
      </div>
      <div className={`flex items-center px-4 py-1.5 border-t border-border-subtle/25 ${hasTranslatedText ? 'justify-between' : 'justify-end'}`}>
        {hasTranslatedText && (
          <button
            onClick={() => handleSpeak(translatedText, targetLang, 'target')}
            disabled={!canUseTts}
            className="p-1.5 rounded-lg text-text-secondary hover:text-accent-magenta transition-colors disabled:opacity-30"
            aria-label="Listen to translation"
            title={canUseTts ? 'Listen to translation' : 'Backend Edge TTS is unavailable'}
          >
            <SpeakerIcon className={`w-4.5 h-4.5 ${ttsLoadingKey === 'target' ? 'animate-pulse' : ''}`} />
          </button>
        )}

        <div className="flex items-center gap-1.5">
          {hasTranslatedText && (
            <button
              onClick={handleCopyTranslation}
              title={copied ? 'Copied' : 'Copy translation'}
              className={`p-1.5 rounded-lg transition-colors ${
                copied
                  ? 'text-accent-magenta bg-accent-magenta/10'
                  : 'text-text-secondary hover:text-accent-magenta'
              }`}
              aria-label="Copy translation"
            >
              <CopyIcon className="w-4 h-4" />
            </button>
          )}

          {/* Counter hidden when empty */}
          <span className={`text-xs tabular-nums transition-opacity duration-200 ${(translatedText || '').length > 0 ? 'text-text-secondary opacity-100' : 'opacity-0'}`}>
            {(translatedText || '').length}
          </span>
        </div>
      </div>
    </div>
  )

  /* ════════════════════════════════════════════════════════════
     Render — two layout branches (desktop / mobile)
     ════════════════════════════════════════════════════════════ */
  return (
    <div className="flex-1 flex flex-col px-4 sm:px-6 py-4 md:py-5 max-w-6xl mx-auto w-full overflow-y-auto">

      {/* ══ DESKTOP ══ (md+) */}
      <div className="hidden md:flex md:flex-col flex-1">
        {/* Language header row — both sides LEFT-aligned */}
        <div className="flex items-center mb-2">
          <div className="flex-1">{sourceLangBar}</div>
          {swapBtn}
          <div className="flex-1">{targetLangBar}</div>
        </div>

        {/* Two-column boxes (equal height via grid) */}
        <div className="grid grid-cols-2 gap-4">
          {renderInputBox()}
          {renderOutputBox()}
        </div>

        {/* Toggle centred below */}
        <div className="flex justify-center mt-3">{toggleSection}</div>
      </div>

      {/* ══ MOBILE ══ (<md) */}
      <div className="flex md:hidden flex-col flex-1 gap-2">
        {sourceLangBar}
        {renderInputBox()}

        {/* Toggle + Swap row */}
        <div className="flex items-center justify-between px-1">
          {toggleSection}
          {swapBtn}
        </div>

        {targetLangBar}
        {renderOutputBox()}
      </div>

      <div className="mt-3 flex flex-col items-center gap-2">
        <div className={`w-full max-w-3xl rounded-xl border px-3 py-2 text-xs ${modeStatus.className}`}>
          {modeStatus.message}
        </div>
        {settingsNotice && (
          <div className="w-full max-w-3xl rounded-xl border border-accent-magenta/40 bg-accent-magenta/10 px-3 py-2 text-xs text-accent-magenta">
            {settingsNotice}
          </div>
        )}
      </div>

      {/* ══ SHARED — Wiki-Voz cards ══ */}
      {wikiData && !selectedTerm && (
        <div className="mt-4 animate-slide-up">
          <div className="bg-bg-card border border-accent-gold/40 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-accent-gold">📖</span>
              <span className="text-accent-gold font-semibold text-xs uppercase tracking-wider">Wiki-Voz</span>
            </div>
            <div className="flex gap-4">
              {wikiData.image_url && (
                <img
                  src={wikiData.image_url}
                  alt={wikiData.term}
                  className="w-20 h-20 rounded-lg object-cover border border-border-subtle shrink-0"
                  onError={(e) => { e.target.style.display = 'none' }}
                />
              )}
              <div>
                <h4 className="text-text-primary font-bold text-lg">{wikiData.term}</h4>
                <p className="text-text-secondary text-sm">{wikiData.definition}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedTerm && (
        <CulturalTermPopup
          entry={selectedTerm}
          onClose={() => setSelectedTerm(null)}
          apiUrl={apiUrl}
          backendUp={backendUp}
          ttsAvailable={ttsAvailable}
        />
      )}
    </div>
  )
}
