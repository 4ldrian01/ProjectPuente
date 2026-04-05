/**
 * TranslateScreen.jsx — Main translation screen (Google Translate-inspired).
 *
 * Desktop  → side-by-side input / output (2-col grid).
 * Mobile   → stacked, scrollable (1-col).
 *
 * Features: controlled language roster, mutual exclusion, swap, backend edge-tts,
 *           character counter (hidden when empty),
 *           formal/street toggle, cultural-term highlighting.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CopyIcon, SpeakerIcon } from '../icons/NavIcons'
import LanguageSelector from '../LanguageSelector'
import CulturalTermPopup from '../CulturalTermPopup'
import { CULTURAL_TERMS_MAP, getCulturalEntry } from '../../data/wikiVozData'
import { loadSettings, SETTINGS_STORAGE_KEY, SETTINGS_UPDATED_EVENT } from '../../lib/settings'
import { withApiKeyHeaders } from '../../lib/apiAuth'
import { speakWithEdgeTts, stopEdgeTtsPlayback } from '../../lib/ttsClient'

/* ── Language config (with Spanish baseline control variable) ── */
const SOURCE_VISIBLE  = ['auto', 'en', 'tl']
const SOURCE_DROPDOWN = ['cbk', 'ceb', 'hil', 'es']
const TARGET_VISIBLE  = ['cbk', 'ceb', 'hil', 'es']
const TARGET_DROPDOWN = ['en', 'tl']

const LANGUAGE_LABELS = {
  auto: 'Auto-Detect',
  en: 'English',
  tl: 'Tagalog',
  cbk: 'Chavacano',
  ceb: 'Cebuano/Bisaya',
  hil: 'Hiligaynon',
  es: 'Spanish',
}

const CHAR_LIMIT = 250

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
  apiKeyRequired = false,
  clientApiKeyConfigured = true,
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
  const [hoveredWikiTerm, setHoveredWikiTerm] = useState(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const [btvlLoading, setBtvlLoading] = useState(false)
  const [btvlError, setBtvlError] = useState('')
  const [btvlResult, setBtvlResult] = useState(null)

  const debounceMs      = 800
  const lastSentKeyRef  = useRef('')
  const forceRef        = useRef(false)
  const sourceTextareaRef = useRef(null)
  const copyResetTimerRef = useRef(null)

  const normalizedText = sourceText.trim()
  const sourceCharCount = sourceText.length
  const hasSourceChars = sourceCharCount > 0
  const isCharLimitExceeded = sourceCharCount > CHAR_LIMIT
  const canTranslate   = normalizedText.length > 0 && !isCharLimitExceeded
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
    setBtvlError('')
    setBtvlResult(null)
    setBtvlLoading(false)
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
  const canVerifyBtvl = apiReady && hasTranslatedText && !btvlLoading

  const modeStatus = useMemo(() => {
    const usagePercent = Math.max(8, Math.min(100, Math.round((sourceCharCount / CHAR_LIMIT) * 100)))

    if (!backendUp) {
      return {
        className: 'border-status-warning-border/80 bg-status-warning-bg/95 text-status-warning-text',
        icon: '⚠️',
        message: `${activeModeLabel} mode is selected. It will apply automatically once the backend is reachable again.`,
        fillPercent: 0,
      }
    }

    if (apiKeyRequired && !clientApiKeyConfigured) {
      return {
        className: 'border-status-warning-border/80 bg-status-warning-bg/95 text-status-warning-text',
        icon: '🔐',
        message: 'Backend write endpoints are API-key protected. Set VITE_PUENTE_API_KEY in frontend/.env before translating.',
        fillPercent: 0,
      }
    }

    if (!nllbLoaded) {
      return {
        className: 'border-status-warning-border/80 bg-status-warning-bg/95 text-status-warning-text',
        icon: '⚠️',
        message: `${activeModeLabel} mode cannot run yet because the local NLLB model is not loaded.`,
        fillPercent: usagePercent,
      }
    }

    if (!loraAdapters.includes(activeMode)) {
      return {
        className: 'border-status-warning-border/80 bg-status-warning-bg/95 text-status-warning-text',
        icon: '🧩',
        message: `${activeModeLabel} mode is available, but its LoRA adapter is not loaded yet. Using the base NLLB model, so the tone may sound more neutral than requested.`,
        fillPercent: 0,
      }
    }

    return {
      className: 'border-status-success-border/80 bg-status-success-bg/95 text-status-success-text',
      icon: '✅',
      message: `${activeModeLabel} register is ready via the ${activeMode} LoRA adapter.`,
      fillPercent: 0,
    }
  }, [activeMode, activeModeLabel, apiKeyRequired, backendUp, clientApiKeyConfigured, loraAdapters, nllbLoaded, sourceCharCount])

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

  const handleVerifyBackTranslation = useCallback(async () => {
    if (!translatedText?.trim() || !apiReady) return

    setBtvlLoading(true)
    setBtvlError('')

    try {
      const response = await fetch(`${apiUrl}/btvl/`, {
        method: 'POST',
        headers: {
          ...withApiKeyHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: translatedText.trim(),
          source_lang: targetLang,
          target_lang: 'en',
        }),
      })

      const payload = await response.json().catch(() => ({}))

      if (!response.ok) {
        const validationMessage = payload?.errors
          ? Object.values(payload.errors).flat().join(' ')
          : ''
        throw new Error(
          payload?.error
          || validationMessage
          || 'Back-translation verification failed.',
        )
      }

      setBtvlResult({
        verifiedText: payload?.verified_text || '',
        latencyMs: payload?.latency_ms ?? null,
        model: payload?.model || 'unknown',
        tokensIn: payload?.tokens_in ?? null,
        tokensOut: payload?.tokens_out ?? null,
        pivotUsed: Boolean(payload?.pivot_used),
      })
    } catch (err) {
      setBtvlResult(null)
      setBtvlError(err?.message || 'Back-translation verification failed.')
    } finally {
      setBtvlLoading(false)
    }
  }, [apiReady, apiUrl, targetLang, translatedText])

  const updateTooltipPosition = useCallback((event) => {
    setTooltipPos({
      x: event.clientX + 16,
      y: event.clientY + 16,
    })
  }, [])

  const handleTermMouseEnter = useCallback((termId, event) => {
    setHoveredWikiTerm(getCulturalEntry(termId))
    updateTooltipPosition(event)
  }, [updateTooltipPosition])

  const handleTermMouseMove = useCallback((event) => {
    updateTooltipPosition(event)
  }, [updateTooltipPosition])

  const handleTermMouseLeave = useCallback(() => {
    setHoveredWikiTerm(null)
  }, [])

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
            onMouseEnter={(event) => handleTermMouseEnter(termId, event)}
            onMouseMove={handleTermMouseMove}
            onMouseLeave={handleTermMouseLeave}
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
    <div className="flex items-center gap-3 rounded-full border border-border-subtle bg-bg-card px-4 py-2 shadow-sm">
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
    <div className={`bg-bg-card border rounded-xl flex flex-col min-h-16 md:min-h-22 transition-colors ${
      isCharLimitExceeded
        ? 'border-status-danger-border/90 focus-within:border-status-danger-border'
        : 'border-border-subtle/90 focus-within:border-accent-magenta/90'
    }`}>
      <textarea
        ref={sourceTextareaRef}
        value={sourceText}
        onChange={(e) => setSourceText(e.target.value)}
        placeholder="Enter text to translate…"
        className="w-full bg-transparent text-text-primary text-base leading-relaxed placeholder-text-secondary/40 resize-none overflow-hidden focus:outline-none px-4 pt-3 pb-1 transition-[height] duration-150 ease-out"
        style={{ minHeight: '48px' }}
        maxLength={CHAR_LIMIT}
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
        {hasSourceChars && (
          <span className={`text-xs tabular-nums ${isCharLimitExceeded ? 'text-status-danger-text' : 'text-text-secondary'}`}>
            {sourceCharCount}/{CHAR_LIMIT} characters
          </span>
        )}
      </div>
      {isCharLimitExceeded && (
        <div className="px-4 pb-2 text-xs text-status-danger-text">
          Character limit exceeded. Reduce input below 250 characters.
        </div>
      )}
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
          <div className="text-text-primary text-base leading-relaxed wrap-break-word" aria-readonly="true">
            {renderHighlightedText()}
          </div>
        ) : (
          <p className="text-text-secondary/40 italic text-base">Translation will appear here…</p>
        )}
        {effectiveError && (
          <div className="mt-2 rounded-lg border border-status-danger-border/80 bg-status-danger-bg/95 px-3 py-1.5 text-sm text-status-danger-text">{effectiveError}</div>
        )}
        {ttsError && (
          <div className="mt-2 rounded-lg border border-status-warning-border/80 bg-status-warning-bg/95 px-3 py-1.5 text-sm text-status-warning-text">{ttsError}</div>
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
              onClick={handleVerifyBackTranslation}
              disabled={!canVerifyBtvl}
              title={apiReady ? 'Verify via Back-Translation' : 'Backend/model is not ready'}
              className="rounded-lg border border-border-subtle px-2 py-1 text-[11px] font-medium text-text-secondary transition-colors hover:text-accent-gold hover:border-accent-gold/60 disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Verify via Back-Translation"
            >
              {btvlLoading ? 'Verifying…' : 'Verify via Back-Translation'}
            </button>
          )}

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

      <div className="border-t border-border-subtle/25 px-4 py-2.5 text-xs sm:text-sm" aria-live="polite">
        {!hasTranslatedText && (
          <span className="text-text-secondary/70">
            BTVL diagnostics appear here after translation.
          </span>
        )}

        {hasTranslatedText && !btvlLoading && !btvlResult && !btvlError && (
          <span className="text-text-secondary/80">
            Click <span className="text-accent-gold">Verify via Back-Translation</span> to run an English semantic check.
          </span>
        )}

        {btvlLoading && (
          <div className="flex items-center gap-2 text-accent-magenta">
            <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>Running Back-Translation Verification Loop…</span>
          </div>
        )}

        {btvlError && !btvlLoading && (
          <div className="rounded-lg border border-status-danger-border/80 bg-status-danger-bg/95 px-2.5 py-1.5 text-status-danger-text">
            BTVL error: {btvlError}
          </div>
        )}

        {btvlResult?.verifiedText && !btvlLoading && (
          <div className="space-y-1.5">
            <p className="text-accent-gold font-semibold">Back-Translation (English)</p>
            <p className="text-text-primary leading-relaxed">{btvlResult.verifiedText}</p>
            <p className="text-text-secondary text-[11px]">
              Model: <span className="text-text-primary">{btvlResult.model}</span>
              {' '}| Latency: <span className="text-text-primary">{btvlResult.latencyMs ?? 0}ms</span>
              {' '}| Tokens: <span className="text-text-primary">{btvlResult.tokensIn ?? 0} → {btvlResult.tokensOut ?? 0}</span>
              {' '}| Pivot: <span className="text-text-primary">{btvlResult.pivotUsed ? 'Yes' : 'No'}</span>
            </p>
          </div>
        )}
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
        {/* Top-center sociolinguistic toggle */}
        <div className="mb-3 flex justify-center">{toggleSection}</div>

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
        <div
          className={`w-full max-w-3xl rounded-xl border px-3 py-2.5 text-xs spring-nav-transition ${modeStatus.className}`}
        >
          <div className="flex items-start gap-2">
            <span className="text-[13px] leading-none" aria-hidden="true">{modeStatus.icon}</span>
            <span className="leading-relaxed">{modeStatus.message}</span>
          </div>

          {modeStatus.fillPercent > 0 && (
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-subtle/30" aria-hidden="true">
              <span
                className="block h-full rounded-full bg-status-warning-border/80 spring-indicator-transition"
                style={{ width: `${modeStatus.fillPercent}%` }}
              />
            </div>
          )}
        </div>
        {settingsNotice && (
          <div className="w-full max-w-3xl rounded-xl border border-status-info-border/55 bg-status-info-bg/95 px-3 py-2 text-xs text-status-info-text">
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

      {hoveredWikiTerm && (
        <div
          className="pointer-events-none fixed z-50 max-w-xs rounded-lg border border-accent-gold/40 bg-bg-card/95 px-3 py-2 shadow-xl backdrop-blur-sm"
          style={{ left: tooltipPos.x, top: tooltipPos.y }}
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-accent-gold">Wiki-Voz</p>
          <p className="mt-1 text-sm font-semibold text-text-primary">{hoveredWikiTerm.term}</p>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">{hoveredWikiTerm.definition}</p>
        </div>
      )}
    </div>
  )
}
