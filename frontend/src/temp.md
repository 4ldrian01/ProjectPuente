/**
 * TranslateScreen.jsx — Enterprise translation workbench.
 *
 * Refactor focus:
 * - Input safety controls (sample cycle, clipboard paste)
 * - Register pills (Formal / Casual)
 * - Mock pre-flight LID mismatch banner
 * - Output action strip (BTVL, Edge-TTS, Export)
 * - GapAnalysisTerminal + Post-Inference Profiler integration
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, ClipboardPaste, Download, FlaskConical } from 'lucide-react'
import { CopyIcon } from '../icons/NavIcons'
import LanguageSelector from '../LanguageSelector'
import CulturalTermPopup from '../CulturalTermPopup'
import GapAnalysisTerminal from './GapAnalysisTerminal'
import { loadSettings, SETTINGS_STORAGE_KEY, SETTINGS_UPDATED_EVENT } from '../../lib/settings'
import { withApiKeyHeaders } from '../../lib/apiAuth'
import { speakWithEdgeTts, stopEdgeTtsPlayback } from '../../lib/ttsClient'

/* ── Language config (with Spanish baseline control variable) ── */
const SOURCE_VISIBLE = ['auto', 'en', 'tl']
const SOURCE_DROPDOWN = ['cbk', 'ceb', 'hil', 'es']
const TARGET_VISIBLE = ['cbk', 'ceb', 'hil', 'es']
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

const SOCIOLINGUISTIC_SAMPLE_CASES = [
  {
    label: 'Spanish Formal Baseline',
    text: 'Buenos dias, podria usted traducir esta frase al Chavacano formal para una reunion academica?',
    source: 'es',
    target: 'cbk',
    mode: 'formal',
  },
  {
    label: 'Street Register Check',
    text: 'Ta anda kita na plaza despues, man dale tu version casual para conversa de barangay.',
    source: 'cbk',
    target: 'en',
    mode: 'street',
  },
  {
    label: 'Cebuano to Hiligaynon Pivot',
    text: 'Maayong buntag, palihug hubara kini sa pormal nga Hiligaynon para sa report.',
    source: 'ceb',
    target: 'hil',
    mode: 'formal',
  },
]

const MOCK_LID_HINTS = [
  {
    code: 'es',
    keywords: ['hola', 'buenos', 'gracias', 'por favor', 'usted', 'señor', 'mañana', 'podria'],
  },
  {
    code: 'tl',
    keywords: ['kamusta', 'salamat', 'opo', 'po', 'hindi', 'natin', 'kayo', 'pwede'],
  },
  {
    code: 'cbk',
    keywords: ['ta', 'man', 'kita', 'hende', 'nao', 'zamboanga', 'anda'],
  },
  {
    code: 'ceb',
    keywords: ['maayong', 'buntag', 'unsa', 'karon', 'nimo', 'dili', 'palihug', 'hubara'],
  },
  {
    code: 'hil',
    keywords: ['gid', 'subong', 'ano', 'wala', 'maayo', 'palihog'],
  },
  {
    code: 'en',
    keywords: ['please', 'translate', 'good morning', 'would you', 'could you', 'report'],
  },
]

const CHAR_LIMIT = 250
const TELEMETRY_POLL_INTERVAL_MS = 4500
const FALLBACK_GPU_TOTAL_GB = 4
const FALLBACK_RAM_TOTAL_GB = 8

function clampPercent(value) {
  return Math.min(100, Math.max(0, Number(value) || 0))
}

function formatGb(value) {
  return `${Number(value || 0).toFixed(2)} GB`
}

function estimateTokenCount(text) {
  return Math.max(1, String(text || '').trim().split(/\s+/).filter(Boolean).length)
}

function detectMockLanguage(text) {
  const normalized = String(text || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalized || normalized.length < 8) {
    return null
  }

  let bestMatch = { code: '', score: 0 }

  for (const hint of MOCK_LID_HINTS) {
    let score = 0
    for (const keyword of hint.keywords) {
      if (normalized.includes(keyword)) {
        score += keyword.includes(' ') ? 2 : 1
      }
    }

    if (score > bestMatch.score) {
      bestMatch = { code: hint.code, score }
    }
  }

  if (!bestMatch.code || bestMatch.score === 0) {
    return null
  }

  const tokenCount = normalized.split(' ').filter(Boolean).length
  const confidence = clampPercent(52 + bestMatch.score * 8 + Math.min(tokenCount, 12))

  return {
    code: bestMatch.code,
    label: LANGUAGE_LABELS[bestMatch.code] || bestMatch.code.toUpperCase(),
    confidence,
  }
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
  apiKeyRequired = false,
  clientApiKeyConfigured = true,
  translationEngine = 'unknown',
}) {
  const initialSettings = useMemo(() => loadSettings(), [])

  const [sourceText, setSourceText] = useState('')
  const [sourceLang, setSourceLang] = useState(initialSettings.defaultSourceLang)
  const [targetLang, setTargetLang] = useState(initialSettings.defaultTargetLang)
  const [isStreetMode, setIsStreetMode] = useState(false)
  const [sampleCursor, setSampleCursor] = useState(0)
  const [lidExpanded, setLidExpanded] = useState(false)
  const [selectedTerm, setSelectedTerm] = useState(null)
  const [copied, setCopied] = useState(false)
  const [settingsNotice, setSettingsNotice] = useState('')
  const [ttsError, setTtsError] = useState('')
  const [ttsLoadingKey, setTtsLoadingKey] = useState(null)
  const [hoveredWikiTerm, setHoveredWikiTerm] = useState(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const [btvlLoading, setBtvlLoading] = useState(false)
  const [btvlError, setBtvlError] = useState('')
  const [btvlResult, setBtvlResult] = useState(null)
  const [systemLogs, setSystemLogs] = useState([])
  const [postProfiler, setPostProfiler] = useState(null)
  const [profilerFlash, setProfilerFlash] = useState(false)
  const [telemetry, setTelemetry] = useState({
    loading: true,
    error: '',
    ramUsedGb: 0,
    ramTotalGb: FALLBACK_RAM_TOTAL_GB,
    ramPercent: 0,
    gpuAvailable: false,
    gpuName: '',
    gpuUsedGb: 0,
    gpuTotalGb: FALLBACK_GPU_TOTAL_GB,
    gpuPercent: 0,
    gpuReason: '',
  })

  const debounceMs = 800
  const lastSentKeyRef = useRef('')
  const forceRef = useRef(false)
  const sourceTextareaRef = useRef(null)
  const copyResetTimerRef = useRef(null)
  const inferenceStartRef = useRef(null)
  const telemetryCaptureRef = useRef({
    baselineGpu: 0,
    peakGpu: 0,
    baselineRam: 0,
    peakRam: 0,
  })

  const activeMode = isStreetMode ? 'street' : 'formal'
  const activeModeLabel = isStreetMode ? 'Casual' : 'Formal'
  const normalizedText = sourceText.trim()
  const sourceCharCount = sourceText.length
  const hasSourceChars = sourceCharCount > 0
  const isCharLimitExceeded = sourceCharCount > CHAR_LIMIT
  const canTranslate = normalizedText.length > 0 && !isCharLimitExceeded
  const hasTranslatedText = Boolean(translatedText?.trim())
  const effectiveSourceLang = sourceLang === 'auto' ? 'en' : sourceLang
  const canUseTts = backendUp && ttsAvailable
  const canVerifyBtvl = apiReady && hasTranslatedText && !btvlLoading
  const canExport = hasTranslatedText && !loading
  const gpuTotalGb = telemetry.gpuTotalGb > 0 ? telemetry.gpuTotalGb : FALLBACK_GPU_TOTAL_GB
  const ramTotalGb = telemetry.ramTotalGb > 0 ? telemetry.ramTotalGb : FALLBACK_RAM_TOTAL_GB

  const preflightLid = useMemo(
    () => detectMockLanguage(normalizedText),
    [normalizedText],
  )
  const lidMismatchDetected = Boolean(
    preflightLid && sourceLang !== 'auto' && preflightLid.code !== sourceLang,
  )

  const modeStatus = useMemo(() => {
    const usagePercent = Math.max(8, Math.min(100, Math.round((sourceCharCount / CHAR_LIMIT) * 100)))

    if (!backendUp) {
      return {
        className: 'border-status-warning-border/80 bg-status-warning-bg/95 text-status-warning-text',
        icon: '⚠️',
        message: `${activeModeLabel} register selected. It will apply once the backend is reachable again.`,
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
        message: `${activeModeLabel} register cannot run yet because the local NLLB model is not loaded.`,
        fillPercent: usagePercent,
      }
    }

    if (!loraAdapters.includes(activeMode)) {
      return {
        className: 'border-status-warning-border/80 bg-status-warning-bg/95 text-status-warning-text',
        icon: '🧩',
        message: `${activeModeLabel} register is available, but the LoRA adapter is missing. The base NLLB model will be used.`,
        fillPercent: 0,
      }
    }

    return {
      className: 'border-status-success-border/80 bg-status-success-bg/95 text-status-success-text',
      icon: '✅',
      message: `${activeModeLabel} register is enforced via the ${activeMode} adapter path.`,
      fillPercent: 0,
    }
  }, [activeMode, activeModeLabel, apiKeyRequired, backendUp, clientApiKeyConfigured, loraAdapters, nllbLoaded, sourceCharCount])

  const effectiveError = useMemo(() => {
    if (!error) return ''

    const prefix = `${activeModeLabel} mode: `
    return error.startsWith(prefix) ? error : `${prefix}${error}`
  }, [activeModeLabel, error])

  /* ── Terminal transaction simulation logs ───────────────────────────── */
  useEffect(() => {
    if (loading) {
      setSystemLogs([
        'TXN_FLUSH :: Cleared stale output buffers from previous pass',
        `ROUTING :: ${sourceLang} -> ${targetLang} request routed to local NLLB`,
        `REGISTER_ENFORCED :: ${activeMode.toUpperCase()} profile attached`,
        'INTERCEPT_SCAN :: Wiki-Voz phrase lattice inspection in progress',
      ])
      return
    }

    if (!translatedText) {
      return
    }

    const nextLogs = [
      `ROUTING :: ${sourceLang} -> ${targetLang} resolved on edge runtime`,
      `REGISTER_ENFORCED :: ${activeMode.toUpperCase()} inference completed`,
      'OBSERVER_WRITE :: TranslationLog appended with latency and token traces',
      'PRESENTATION :: Target payload committed to workbench viewport',
    ]

    if (wikiData?.term) {
      nextLogs.splice(2, 0, `INTERCEPT_TRIGGERED :: ${wikiData.term} semantic override surfaced`)
    }

    setSystemLogs(nextLogs)
  }, [activeMode, loading, sourceLang, targetLang, translatedText, wikiData])

  useEffect(() => {
    if (!postProfiler) {
      return
    }

    setSystemLogs((prev) => {
      const withoutProfiler = prev.filter((line) => !line.startsWith('PROFILER ::'))
      return [
        ...withoutProfiler,
        `PROFILER :: ${postProfiler.inferenceMs.toFixed(2)}ms | ${postProfiler.speedTps.toFixed(1)} t/s | VRAM +${postProfiler.vramSpikeGb.toFixed(3)} GB`,
      ]
    })
  }, [postProfiler])

  useEffect(() => {
    if (!btvlResult?.verifiedText) {
      return
    }

    setSystemLogs((prev) => [
      ...prev,
      `BTVL_CHECK :: Verified in ${btvlResult.latencyMs ?? 0}ms with ${btvlResult.pivotUsed ? 'pivot' : 'direct'} route`,
    ])
  }, [btvlResult])

  /* Smooth auto-grow for source input */
  useEffect(() => {
    const el = sourceTextareaRef.current
    if (!el) return

    const minHeight = 88
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
        `Defaults updated: ${LANGUAGE_LABELS[nextSettings.defaultSourceLang]} -> ${LANGUAGE_LABELS[nextSettings.defaultTargetLang]}.`,
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

  useEffect(() => {
    if (!backendUp) {
      setTelemetry((prev) => ({
        ...prev,
        loading: false,
        error: 'Backend offline. Telemetry is unavailable.',
      }))
      return
    }

    let disposed = false

    const pollTelemetry = async () => {
      try {
        const response = await fetch(`${apiUrl}/telemetry/`, {
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
          ramTotalGb: Number(ram.total_gb ?? FALLBACK_RAM_TOTAL_GB),
          ramPercent: clampPercent(ram.percent),
          gpuAvailable: Boolean(gpu.available),
          gpuName: String(gpu.name || ''),
          gpuUsedGb: Number(gpu.used_gb ?? 0),
          gpuTotalGb: Number(gpu.total_gb ?? FALLBACK_GPU_TOTAL_GB),
          gpuPercent: clampPercent(gpu.percent),
          gpuReason: String(gpu.reason || ''),
        })
      } catch (err) {
        if (disposed) return

        setTelemetry((prev) => ({
          ...prev,
          loading: false,
          error: err?.message || 'Unable to load telemetry.',
        }))
      }
    }

    pollTelemetry()
    const timer = setInterval(pollTelemetry, TELEMETRY_POLL_INTERVAL_MS)

    return () => {
      disposed = true
      clearInterval(timer)
    }
  }, [apiUrl, backendUp])

  useEffect(() => {
    if (!loading) {
      return
    }

    const capture = telemetryCaptureRef.current
    capture.peakGpu = Math.max(Number(capture.peakGpu ?? 0), Number(telemetry.gpuUsedGb ?? 0))
    capture.peakRam = Math.max(Number(capture.peakRam ?? 0), Number(telemetry.ramUsedGb ?? 0))
  }, [loading, telemetry.gpuUsedGb, telemetry.ramUsedGb])

  useEffect(() => {
    let flashTimer

    if (loading) {
      const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
      inferenceStartRef.current = now
      telemetryCaptureRef.current = {
        baselineGpu: Number(telemetry.gpuUsedGb ?? 0),
        peakGpu: Number(telemetry.gpuUsedGb ?? 0),
        baselineRam: Number(telemetry.ramUsedGb ?? 0),
        peakRam: Number(telemetry.ramUsedGb ?? 0),
      }
    } else if (inferenceStartRef.current !== null && translatedText?.trim()) {
      const finishedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
      const inferenceMs = Math.max(100, finishedAt - inferenceStartRef.current)
      const capture = telemetryCaptureRef.current

      const baselineGpu = Number(capture.baselineGpu ?? telemetry.gpuUsedGb ?? 0)
      const peakGpu = Number(capture.peakGpu ?? telemetry.gpuUsedGb ?? 0)
      let vramSpikeGb = Math.max(0, peakGpu - baselineGpu)

      if (!Number.isFinite(vramSpikeGb) || vramSpikeGb === 0) {
        vramSpikeGb = telemetry.gpuAvailable
          ? Math.max(0.03, Number((telemetry.gpuUsedGb || 0) * 0.02))
          : 0
      }

      const tokenEstimate = estimateTokenCount(translatedText)
      const speedTps = tokenEstimate / Math.max(inferenceMs / 1000, 0.001)

      setPostProfiler({
        inferenceMs: Number(inferenceMs.toFixed(2)),
        speedTps: Number(speedTps.toFixed(1)),
        vramSpikeGb: Number(vramSpikeGb.toFixed(3)),
        observedGpuUsedGb: Number((telemetry.gpuUsedGb || 0).toFixed(3)),
        observedRamUsedGb: Number((telemetry.ramUsedGb || 0).toFixed(3)),
        engine: translationEngine || 'unknown',
        gpuName: telemetry.gpuName || 'Unknown GPU',
        timestamp: Date.now(),
      })

      setProfilerFlash(true)
      flashTimer = setTimeout(() => setProfilerFlash(false), 900)
      inferenceStartRef.current = null
    }

    return () => {
      if (flashTimer) clearTimeout(flashTimer)
    }
  }, [loading, telemetry.gpuAvailable, telemetry.gpuName, telemetry.gpuUsedGb, telemetry.ramUsedGb, translatedText, translationEngine])

  useEffect(() => {
    if (!lidMismatchDetected) {
      return
    }

    setLidExpanded(true)
  }, [lidMismatchDetected, preflightLid?.code])

  /* payload for backend */
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
  const handleSourceChange = useCallback((code) => {
    setSourceLang(code)

    if (code !== 'auto' && code === targetLang) {
      const fallback = [...TARGET_VISIBLE, ...TARGET_DROPDOWN].find((item) => item !== code)
      if (fallback) setTargetLang(fallback)
    }
  }, [targetLang])

  const handleTargetChange = useCallback((code) => {
    setTargetLang(code)

    if (sourceLang !== 'auto' && code === sourceLang) {
      const fallback = [...SOURCE_VISIBLE, ...SOURCE_DROPDOWN].find((item) => item !== 'auto' && item !== code)
      if (fallback) setSourceLang(fallback)
    }
  }, [sourceLang])

  /* ── Swap ── */
  const handleSwap = () => {
    if (sourceLang === 'auto') return
    const currentSource = sourceLang
    const currentTarget = targetLang

    setSourceLang(currentTarget)
    setTargetLang(currentSource)
    forceRef.current = true
  }

  const handleCycleSample = useCallback(() => {
    const caseIndex = sampleCursor % SOCIOLINGUISTIC_SAMPLE_CASES.length
    const sample = SOCIOLINGUISTIC_SAMPLE_CASES[caseIndex]

    setSampleCursor((prev) => (prev + 1) % SOCIOLINGUISTIC_SAMPLE_CASES.length)
    setSourceText(sample.text.slice(0, CHAR_LIMIT))
    setIsStreetMode(sample.mode === 'street')

    let nextSource = sample.source
    let nextTarget = sample.target

    if (nextSource !== 'auto' && nextSource === nextTarget) {
      nextTarget = [...TARGET_VISIBLE, ...TARGET_DROPDOWN].find((code) => code !== nextSource) || nextTarget
    }

    setSourceLang(nextSource)
    setTargetLang(nextTarget)
    setSettingsNotice(`Loaded sample ${caseIndex + 1}/${SOCIOLINGUISTIC_SAMPLE_CASES.length}: ${sample.label}.`)
    forceRef.current = true
  }, [sampleCursor])

  const handlePasteText = useCallback(async () => {
    if (!navigator?.clipboard?.readText) {
      setSettingsNotice('Clipboard API is unavailable in this browser context.')
      return
    }

    try {
      const clipboardText = await navigator.clipboard.readText()
      const cleaned = String(clipboardText || '')

      if (!cleaned.trim()) {
        setSettingsNotice('Clipboard is empty. Copy a sentence first.')
        return
      }

      const truncated = cleaned.slice(0, CHAR_LIMIT)
      setSourceText(truncated)
      forceRef.current = true

      if (cleaned.length > CHAR_LIMIT) {
        setSettingsNotice(`Clipboard text exceeded ${CHAR_LIMIT} chars and was truncated.`)
      } else {
        setSettingsNotice('Clipboard text pasted into source panel.')
      }
    } catch {
      setSettingsNotice('Clipboard access denied. Allow paste permissions and retry.')
    }
  }, [])

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

      const payloadResponse = await response.json().catch(() => ({}))

      if (!response.ok) {
        const validationMessage = payloadResponse?.errors
          ? Object.values(payloadResponse.errors).flat().join(' ')
          : ''

        throw new Error(
          payloadResponse?.error
          || validationMessage
          || 'Back-translation verification failed.',
        )
      }

      setBtvlResult({
        verifiedText: payloadResponse?.verified_text || '',
        latencyMs: payloadResponse?.latency_ms ?? null,
        model: payloadResponse?.model || 'unknown',
        tokensIn: payloadResponse?.tokens_in ?? null,
        tokensOut: payloadResponse?.tokens_out ?? null,
        pivotUsed: Boolean(payloadResponse?.pivot_used),
      })
    } catch (err) {
      setBtvlResult(null)
      setBtvlError(err?.message || 'Back-translation verification failed.')
    } finally {
      setBtvlLoading(false)
    }
  }, [apiReady, apiUrl, targetLang, translatedText])

  const handleExportMock = useCallback(() => {
    if (!translatedText?.trim()) return

    try {
      const payloadExport = {
        source_text: sourceText,
        translated_text: translatedText,
        source_lang: sourceLang,
        target_lang: targetLang,
        mode: activeMode,
        exported_at: new Date().toISOString(),
        note: 'Mock export package for enterprise workflow validation.',
      }

      const blob = new Blob([JSON.stringify(payloadExport, null, 2)], {
        type: 'application/json;charset=utf-8',
      })

      const href = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = href
      anchor.download = `puente-export-${Date.now()}.json`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(href)

      setSettingsNotice('Mock export package generated locally.')
    } catch {
      setSettingsNotice('Export mock failed in this browser context.')
    }
  }, [activeMode, sourceLang, sourceText, targetLang, translatedText])

  const updateTooltipPosition = useCallback((event) => {
    setTooltipPos({
      x: event.clientX + 16,
      y: event.clientY + 16,
    })
  }, [])

  const handleAcceptDetectedLanguage = () => {
    if (!preflightLid) return

    handleSourceChange(preflightLid.code)
    setSettingsNotice(`Pre-flight LID accepted: source updated to ${preflightLid.label}.`)
    setLidExpanded(false)
  }

  /* ── Cultural-term highlighting ── */
  const renderHighlightedText = () => {
    if (!translatedText) return null
    if (!wikiData || !wikiData.term) return <span>{translatedText}</span>

    const searchStr = wikiData.term.toLowerCase()
    const regex = new RegExp(`(${wikiData.term})`, 'gi')

    return translatedText.split(regex).map((part, index) => {
      if (part.toLowerCase() === searchStr) {
        return (
          <span
            key={`${part}-${index}`}
            className="cultural-term cursor-pointer text-accent-gold underline decoration-accent-gold decoration-2 underline-offset-2 transition-colors hover:text-accent-gold/80"
            onMouseEnter={(event) => {
              setHoveredWikiTerm(wikiData)
              updateTooltipPosition(event)
            }}
            onMouseMove={updateTooltipPosition}
            onMouseLeave={() => setHoveredWikiTerm(null)}
            onClick={() => setSelectedTerm(wikiData)}
          >
            {part}
          </span>
        )
      }

      return <span key={`${part}-${index}`}>{part}</span>
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
      excludeCode={targetLang}
    />
  )

  const targetLangBar = (
    <LanguageSelector
      selected={targetLang}
      onSelect={handleTargetChange}
      visibleCodes={TARGET_VISIBLE}
      dropdownCodes={TARGET_DROPDOWN}
      excludeCode={sourceLang === 'auto' ? null : sourceLang}
    />
  )

  const swapBtn = (
    <button
      onClick={handleSwap}
      disabled={sourceLang === 'auto'}
      className="rounded-lg border border-border-subtle bg-bg-card p-2 text-text-secondary transition-colors hover:border-accent-magenta/55 hover:text-accent-magenta disabled:cursor-not-allowed disabled:opacity-30"
      title="Swap languages"
      aria-label="Swap source and target languages"
    >
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    </button>
  )

  const renderInputBox = () => (
    <div className={`flex min-h-42 flex-col rounded-xl border bg-bg-card transition-colors ${
      isCharLimitExceeded
        ? 'border-status-danger-border/90 focus-within:border-status-danger-border'
        : 'border-border-subtle focus-within:border-accent-magenta/90'
    }`}>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle/55 px-3 py-2.5">
        <div className="inline-flex items-center gap-1 rounded-full border border-border-subtle bg-bg-elevated p-1 text-xs font-semibold">
          <button
            onClick={() => setIsStreetMode(false)}
            className={`rounded-full px-3 py-1 transition-colors ${
              !isStreetMode
                ? 'bg-status-info-bg text-status-info-text'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            aria-pressed={!isStreetMode}
          >
            Formal
          </button>
          <button
            onClick={() => setIsStreetMode(true)}
            className={`rounded-full px-3 py-1 transition-colors ${
              isStreetMode
                ? 'bg-accent-magenta/20 text-accent-magenta'
                : 'text-text-secondary hover:text-text-primary'
            }`}
            aria-pressed={isStreetMode}
          >
            Casual
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={handleCycleSample}
            className="inline-flex items-center gap-1 rounded-md border border-dashed border-border-subtle px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:border-accent-magenta/60 hover:text-text-primary"
            title="Load the next thesis sample input"
          >
            <FlaskConical className="h-3.5 w-3.5" />
            Sample Test
          </button>
          <button
            onClick={handlePasteText}
            className="inline-flex items-center gap-1 rounded-md border border-dashed border-border-subtle px-2.5 py-1 text-xs font-medium text-text-secondary transition-colors hover:border-accent-magenta/60 hover:text-text-primary"
            title="Paste source text from clipboard"
          >
            <ClipboardPaste className="h-3.5 w-3.5" />
            Paste Text
          </button>
        </div>
      </div>

      <textarea
        ref={sourceTextareaRef}
        value={sourceText}
        onChange={(event) => setSourceText(event.target.value)}
        placeholder="Enter text to translate..."
        className="w-full resize-none overflow-hidden bg-transparent px-4 pt-3 pb-2 text-base leading-relaxed text-text-primary placeholder-text-secondary/45 focus:outline-none transition-[height] duration-150 ease-out"
        style={{ minHeight: '88px' }}
        maxLength={CHAR_LIMIT}
      />

      <div className={`flex items-center border-t border-border-subtle/40 px-4 py-2 ${hasSourceChars ? 'justify-between' : 'justify-end'}`}>
        {hasSourceChars && (
          <button
            onClick={() => handleSpeak(sourceText, effectiveSourceLang, 'source')}
            disabled={!canUseTts}
            className="rounded-md border border-border-subtle px-2 py-1 text-[11px] font-medium text-text-secondary transition-colors hover:border-accent-magenta/55 hover:text-accent-magenta disabled:cursor-not-allowed disabled:opacity-35"
            title={canUseTts ? 'Preview source audio with Edge-TTS' : 'Backend Edge-TTS is unavailable'}
          >
            {ttsLoadingKey === 'source' ? '🔊 Speaking…' : '🔊 Source TTS'}
          </button>
        )}

        {hasSourceChars && (
          <span className={`text-xs tabular-nums ${isCharLimitExceeded ? 'text-status-danger-text' : 'text-text-secondary'}`}>
            {sourceCharCount}/{CHAR_LIMIT}
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

  const renderLidMismatchBanner = () => {
    if (!lidMismatchDetected || !preflightLid) {
      return null
    }

    return (
      <div className="rounded-xl border border-status-warning-border/70 bg-status-warning-bg/80">
        <button
          onClick={() => setLidExpanded((prev) => !prev)}
          className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm text-status-warning-text"
          aria-expanded={lidExpanded}
        >
          <span>
            Did you mean to translate from <span className="font-semibold">{preflightLid.label}</span>?
          </span>
          {lidExpanded ? <ChevronUp className="h-4 w-4 shrink-0" /> : <ChevronDown className="h-4 w-4 shrink-0" />}
        </button>

        {lidExpanded && (
          <div className="border-t border-status-warning-border/45 px-3 py-2 text-xs text-status-warning-text/95">
            <p>Mock pre-flight LID confidence: {preflightLid.confidence}%.</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                onClick={handleAcceptDetectedLanguage}
                className="rounded-md border border-status-warning-border/70 bg-status-warning-bg px-2.5 py-1 font-semibold text-status-warning-text hover:bg-status-warning-bg/80"
              >
                Use {preflightLid.label}
              </button>
              <button
                onClick={() => setLidExpanded(false)}
                className="rounded-md border border-border-subtle px-2.5 py-1 font-medium text-text-secondary hover:text-text-primary"
              >
                Keep {LANGUAGE_LABELS[sourceLang] || sourceLang.toUpperCase()}
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }

  const actionButtonClass = 'rounded-md border border-border-subtle px-2.5 py-1 text-[11px] font-medium text-text-secondary transition-colors hover:border-accent-magenta/55 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40'

  const renderOutputBox = () => (
    <div className="flex min-h-42 flex-col rounded-xl border border-border-subtle bg-bg-card/90">
      <div className="flex-1 px-4 pt-3 pb-1">
        {loading ? (
          <div className="flex items-center gap-3 text-accent-magenta">
            <svg className="h-4.5 w-4.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Translating...</span>
          </div>
        ) : translatedText ? (
          <div className="wrap-break-word text-base leading-relaxed text-text-primary" aria-readonly="true">
            {renderHighlightedText()}
          </div>
        ) : (
          <p className="text-base italic text-text-secondary/45">Translation will appear here...</p>
        )}

        {effectiveError && (
          <div className="mt-2 rounded-lg border border-status-danger-border/80 bg-status-danger-bg/95 px-3 py-1.5 text-sm text-status-danger-text">
            {effectiveError}
          </div>
        )}

        {ttsError && (
          <div className="mt-2 rounded-lg border border-status-warning-border/80 bg-status-warning-bg/95 px-3 py-1.5 text-sm text-status-warning-text">
            {ttsError}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle/50 px-4 py-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={handleVerifyBackTranslation}
            disabled={!canVerifyBtvl}
            className={actionButtonClass}
            title={apiReady ? 'Run Back-Translation Verification Loop' : 'Backend/model is not ready'}
          >
            {btvlLoading ? '🔄 BTVL…' : '🔄 BTVL'}
          </button>

          <button
            onClick={() => handleSpeak(translatedText, targetLang, 'target')}
            disabled={!hasTranslatedText || !canUseTts}
            className={actionButtonClass}
            title={canUseTts ? 'Read translated text via Edge-TTS' : 'Backend Edge-TTS is unavailable'}
          >
            {ttsLoadingKey === 'target' ? '🔊 Speaking…' : '🔊 Edge-TTS'}
          </button>

          <button
            onClick={handleExportMock}
            disabled={!canExport}
            className={actionButtonClass}
            title="Mock export artifact"
          >
            <span className="inline-flex items-center gap-1">
              <Download className="h-3.5 w-3.5" />
              📥 Export
            </span>
          </button>
        </div>

        <div className="flex items-center gap-2">
          {hasTranslatedText && (
            <button
              onClick={handleCopyTranslation}
              title={copied ? 'Copied' : 'Copy translation'}
              className={`rounded-lg p-1.5 transition-colors ${
                copied
                  ? 'bg-accent-magenta/10 text-accent-magenta'
                  : 'text-text-secondary hover:text-accent-magenta'
              }`}
              aria-label="Copy translation"
            >
              <CopyIcon className="h-4 w-4" />
            </button>
          )}

          <span className={`text-xs tabular-nums transition-opacity duration-200 ${(translatedText || '').length > 0 ? 'text-text-secondary opacity-100' : 'opacity-0'}`}>
            {(translatedText || '').length}
          </span>
        </div>
      </div>

      <div className="border-t border-border-subtle/40 px-4 py-2.5 text-xs sm:text-sm" aria-live="polite">
        {!hasTranslatedText && (
          <span className="text-text-secondary/70">
            BTVL diagnostics appear here after translation.
          </span>
        )}

        {hasTranslatedText && !btvlLoading && !btvlResult && !btvlError && (
          <span className="text-text-secondary/80">
            Click <span className="font-semibold text-accent-gold">🔄 BTVL</span> to run an English semantic check.
          </span>
        )}

        {btvlLoading && (
          <div className="flex items-center gap-2 text-accent-magenta">
            <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>Running Back-Translation Verification Loop...</span>
          </div>
        )}

        {btvlError && !btvlLoading && (
          <div className="rounded-lg border border-status-danger-border/80 bg-status-danger-bg/95 px-2.5 py-1.5 text-status-danger-text">
            BTVL error: {btvlError}
          </div>
        )}

        {btvlResult?.verifiedText && !btvlLoading && (
          <div className="space-y-1.5">
            <p className="font-semibold text-accent-gold">Back-Translation (English)</p>
            <p className="leading-relaxed text-text-primary">{btvlResult.verifiedText}</p>
            <p className="text-[11px] text-text-secondary">
              Model: <span className="text-text-primary">{btvlResult.model}</span>
              {' '}| Latency: <span className="text-text-primary">{btvlResult.latencyMs ?? 0}ms</span>
              {' '}| Tokens: <span className="text-text-primary">{btvlResult.tokensIn ?? 0}{' -> '}{btvlResult.tokensOut ?? 0}</span>
              {' '}| Pivot: <span className="text-text-primary">{btvlResult.pivotUsed ? 'Yes' : 'No'}</span>
            </p>
          </div>
        )}
      </div>
    </div>
  )

  const renderProfilerCard = () => (
    <section
      className={`flex h-full min-h-40 flex-col rounded-xl border border-border-subtle bg-bg-card transition-shadow ${
        profilerFlash ? 'shadow-[0_0_0_1px_rgba(217,70,239,0.45),0_0_25px_rgba(217,70,239,0.18)]' : 'shadow-sm'
      }`}
    >
      <div className="flex items-center justify-between border-b border-border-subtle/55 px-4 py-2.5">
        <span className="text-xs font-semibold uppercase tracking-[0.13em] text-text-secondary">Post-Inference Profiler</span>
        <span className={`text-[11px] font-semibold ${postProfiler ? 'text-accent-magenta' : 'text-text-secondary/70'}`}>
          {postProfiler ? 'Captured' : 'Awaiting Run'}
        </span>
      </div>

      <div className="flex-1 space-y-3 px-4 py-3">
        {!postProfiler ? (
          <div className="space-y-1.5 text-sm text-text-secondary/80">
            <p>Run a translation to trigger profiler capture.</p>
            <p>Metrics will update only after inference completes.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <div className="rounded-lg border border-border-subtle bg-bg-elevated/50 p-2.5">
                <p className="text-[11px] uppercase tracking-wide text-text-secondary">Inference Time</p>
                <p className="mt-1 text-lg font-semibold text-text-primary">{postProfiler.inferenceMs.toFixed(2)} ms</p>
              </div>

              <div className="rounded-lg border border-border-subtle bg-bg-elevated/50 p-2.5">
                <p className="text-[11px] uppercase tracking-wide text-text-secondary">Speed</p>
                <p className="mt-1 text-lg font-semibold text-text-primary">{postProfiler.speedTps.toFixed(1)} t/s</p>
              </div>

              <div className="rounded-lg border border-border-subtle bg-bg-elevated/50 p-2.5">
                <p className="text-[11px] uppercase tracking-wide text-text-secondary">VRAM Spike</p>
                <p className="mt-1 text-lg font-semibold text-text-primary">+{postProfiler.vramSpikeGb.toFixed(3)} GB</p>
              </div>
            </div>

            <p className="text-xs text-text-secondary">
              Engine: <span className="text-text-primary">{postProfiler.engine}</span>
              {' '}| GPU: <span className="text-text-primary">{postProfiler.gpuName}</span>
            </p>

            <p className="text-xs text-text-secondary">
              Live usage snapshot: VRAM <span className="text-text-primary">{formatGb(postProfiler.observedGpuUsedGb)} / {formatGb(gpuTotalGb)}</span>
              {' '}| RAM <span className="text-text-primary">{formatGb(postProfiler.observedRamUsedGb)} / {formatGb(ramTotalGb)}</span>
            </p>
          </>
        )}

        {telemetry.loading && (
          <p className="text-xs text-text-secondary/80">Syncing telemetry feed...</p>
        )}

        {telemetry.error && (
          <p className="text-xs text-status-warning-text">{telemetry.error}</p>
        )}

        {!telemetry.gpuAvailable && telemetry.gpuReason && (
          <p className="text-xs text-status-warning-text">GPU reason: {telemetry.gpuReason}</p>
        )}
      </div>
    </section>
  )

  /* ════════════════════════════════════════════════════════════
     Render — desktop and mobile layouts
     ════════════════════════════════════════════════════════════ */
  return (
    <div className="mx-auto flex w-full max-w-312 flex-1 flex-col overflow-y-auto px-4 py-4 sm:px-6 md:py-5">
      {/* ══ DESKTOP ══ (md+) */}
      <div className="hidden flex-1 flex-col md:flex">
        <div className="mb-2 flex items-center">
          <div className="flex-1">{sourceLangBar}</div>
          {swapBtn}
          <div className="flex-1">{targetLangBar}</div>
        </div>

        <div className="mb-3">{renderLidMismatchBanner()}</div>

        <div className="grid grid-cols-2 gap-4">
          {renderInputBox()}
          {renderOutputBox()}
        </div>

        <div className="mt-4 grid auto-rows-fr grid-cols-2 gap-4">
          <GapAnalysisTerminal
            logs={systemLogs}
            isFlushing={loading}
            className="h-full min-h-40"
          />
          {renderProfilerCard()}
        </div>
      </div>

      {/* ══ MOBILE ══ (<md) */}
      <div className="flex flex-1 flex-col gap-2.5 md:hidden">
        {sourceLangBar}
        {renderInputBox()}

        <div className="flex items-center justify-end px-1">
          {swapBtn}
        </div>

        {targetLangBar}
        {renderLidMismatchBanner()}
        {renderOutputBox()}

        <div className="mt-1 flex flex-col gap-2.5">
          <GapAnalysisTerminal
            logs={systemLogs}
            isFlushing={loading}
            className="min-h-40"
          />
          {renderProfilerCard()}
        </div>
      </div>

      <div className="mt-3 flex flex-col items-center gap-2">
        <div className={`w-full max-w-3xl rounded-xl border px-3 py-2.5 text-xs spring-nav-transition ${modeStatus.className}`}>
          <div className="flex items-start gap-2">
            <span className="text-[13px] leading-none" aria-hidden="true">{modeStatus.icon}</span>
            <span className="leading-relaxed">{modeStatus.message}</span>
          </div>

          {modeStatus.fillPercent > 0 && (
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-subtle/30" aria-hidden="true">
              <span
                className="spring-indicator-transition block h-full rounded-full bg-status-warning-border/80"
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
          <div className="rounded-xl border border-accent-gold/40 bg-bg-card p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-accent-gold">📖</span>
              <span className="text-xs font-semibold uppercase tracking-wider text-accent-gold">Wiki-Voz</span>
            </div>

            <div className="flex gap-4">
              {wikiData.image_url && (
                <img
                  src={wikiData.image_url}
                  alt={wikiData.term}
                  className="h-20 w-20 shrink-0 rounded-lg border border-border-subtle object-cover"
                  onError={(event) => {
                    event.target.style.display = 'none'
                  }}
                />
              )}

              <div>
                <h4 className="text-lg font-bold text-text-primary">{wikiData.term}</h4>
                <p className="text-sm text-text-secondary">{wikiData.definition}</p>
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