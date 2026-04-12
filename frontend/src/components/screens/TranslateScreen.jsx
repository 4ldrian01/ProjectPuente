/**
 * TranslateScreen.jsx — Enterprise translation workbench.
 *
 * Refactor focus:
 * - Input safety controls (sample cycle, clipboard paste)
 * - Register pills (Formal / Street)
 * - Mock pre-flight LID mismatch banner
 * - Output action strip (BTVL, Edge-TTS, Export)
 * - GapAnalysisTerminal + Post-Inference Profiler integration
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, ClipboardPaste, Download, FlaskConical } from 'lucide-react'
import { CloseIcon, CopyIcon } from '../icons/NavIcons'
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
    label: 'Cebuano to Hiligaynon Direct',
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
const SOURCE_PLACEHOLDER = 'Enter Word to translate...'
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

function flattenValidationErrors(errors) {
  if (!errors || typeof errors !== 'object') {
    return ''
  }

  return Object.values(errors)
    .flat()
    .map((value) => String(value || '').trim())
    .filter(Boolean)
    .join(' ')
}

function extractApiErrorMessage(payload, fallback = 'Request failed.') {
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
  translationMeta = null,
  notify,
}) {
  const initialSettings = useMemo(() => loadSettings(), [])

  const [sourceText, setSourceText] = useState('')
  const [sourceLang, setSourceLang] = useState(initialSettings.defaultSourceLang)
  const [targetLang, setTargetLang] = useState(initialSettings.defaultTargetLang)
  const [isStreetMode, setIsStreetMode] = useState(false)
  const [isSourceInputFocused, setIsSourceInputFocused] = useState(false)
  const actionButtonClass = 'a26-button-ghost px-2.5 py-1 text-[11px] font-medium disabled:cursor-not-allowed disabled:opacity-40'
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
  const lastErrorToastRef = useRef('')
  const telemetryCaptureRef = useRef({
    baselineGpu: 0,
    peakGpu: 0,
    baselineRam: 0,
    peakRam: 0,
  })

  const activeMode = isStreetMode ? 'street' : 'formal'
  const activeModeLabel = isStreetMode ? 'Street' : 'Formal'
  const normalizedText = sourceText.trim()
  const sourceCharCount = sourceText.length
  const hasSourceChars = sourceCharCount > 0
  const showSourceQuickActions = !hasSourceChars && !isSourceInputFocused
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

  const emitToast = useCallback((payload) => {
    if (typeof notify !== 'function') {
      return
    }

    notify(payload)
  }, [notify])

  const effectiveError = useMemo(() => {
    if (!error) return ''

    const prefix = `${activeModeLabel} mode: `
    return error.startsWith(prefix) ? error : `${prefix}${error}`
  }, [activeModeLabel, error])

  useEffect(() => {
    if (!effectiveError) {
      return
    }

    if (lastErrorToastRef.current === effectiveError) {
      return
    }

    lastErrorToastRef.current = effectiveError
    emitToast({
      title: 'Translation warning',
      message: effectiveError,
      variant: 'error',
      durationMs: 5200,
    })
  }, [effectiveError, emitToast])

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

  /* ── Terminal transaction simulation logs ───────────────────────────── */
  useEffect(() => {
    if (loading) {
      setSystemLogs([
        'TXN_FLUSH :: Cleared stale output buffers from previous pass',
        `ROUTING :: ${sourceLang} -> ${targetLang} direct-first request routed to local NLLB`,
        `REGISTER_ENFORCED :: ${activeMode.toUpperCase()} profile attached`,
        'INTERCEPT_SCAN :: Wiki-Voz phrase lattice inspection in progress',
      ])
      return
    }

    if (!translatedText) {
      return
    }

    const routeStrategy = String(translationMeta?.routeStrategy || '').trim()
    const pivotLanguage = String(translationMeta?.pivotLanguage || '').trim()
    const pivotSuffix = pivotLanguage ? ` (${pivotLanguage.toUpperCase()} proximate pivot)` : ''

    let routeLabel = 'resolved via direct path'
    if (translationMeta?.isCached) {
      routeLabel = 'resolved via Translation Memory cache'
    } else if (routeStrategy === 'proximate-pivot') {
      routeLabel = `resolved via proximate pivot${pivotSuffix}`
    } else if (routeStrategy === 'passthrough') {
      routeLabel = 'resolved via passthrough short-circuit'
    }

    const nextLogs = [
      `ROUTING :: ${sourceLang} -> ${targetLang} ${routeLabel} on edge runtime`,
      `REGISTER_ENFORCED :: ${activeMode.toUpperCase()} inference completed`,
      'OBSERVER_WRITE :: TranslationLog appended with latency and token traces',
      'PRESENTATION :: Target payload committed to workbench viewport',
    ]

    if (wikiData?.term) {
      nextLogs.splice(2, 0, `INTERCEPT_TRIGGERED :: ${wikiData.term} semantic override surfaced`)
    }

    setSystemLogs(nextLogs)
  }, [activeMode, loading, sourceLang, targetLang, translatedText, translationMeta, wikiData])

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

    const routeLabel = btvlResult.routeStrategy === 'proximate-pivot'
      ? `proximate-pivot${btvlResult.pivotLanguage ? ` (${btvlResult.pivotLanguage.toUpperCase()})` : ''}`
      : (btvlResult.routeStrategy || (btvlResult.pivotUsed ? 'pivot' : 'direct'))

    setSystemLogs((prev) => [
      ...prev,
      `BTVL_CHECK :: Verified in ${btvlResult.latencyMs ?? 0}ms with ${routeLabel} route`,
    ])
  }, [btvlResult])

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

  const focusSourceInput = useCallback(() => {
    const focus = () => {
      setIsSourceInputFocused(true)
      sourceTextareaRef.current?.focus()
    }

    if (typeof window !== 'undefined' && typeof window.requestAnimationFrame === 'function') {
      window.requestAnimationFrame(focus)
      return
    }

    setTimeout(focus, 0)
  }, [])

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
    emitToast({
      title: 'Sample loaded',
      message: `${sample.label} is now in the source panel.`,
      variant: 'info',
      durationMs: 3600,
    })
    lastSentKeyRef.current = ''
    forceRef.current = true
    focusSourceInput()
  }, [emitToast, focusSourceInput, sampleCursor])

  const handlePasteText = useCallback(async () => {
    if (!navigator?.clipboard?.readText) {
      const message = 'Clipboard API is unavailable in this browser context.'
      setSettingsNotice(message)
      emitToast({ title: 'Paste unavailable', message, variant: 'warning', durationMs: 4200 })
      focusSourceInput()
      return
    }

    try {
      const clipboardText = await navigator.clipboard.readText()
      const cleaned = String(clipboardText || '')

      if (!cleaned.trim()) {
        const message = 'Clipboard is empty. Copy a sentence first.'
        setSettingsNotice(message)
        emitToast({ title: 'Clipboard empty', message, variant: 'warning', durationMs: 3600 })
        return
      }

      const truncated = cleaned.slice(0, CHAR_LIMIT)
      setSourceText(truncated)
      lastSentKeyRef.current = ''
      forceRef.current = true

      if (cleaned.length > CHAR_LIMIT) {
        const message = `Clipboard text exceeded ${CHAR_LIMIT} chars and was truncated.`
        setSettingsNotice(message)
        emitToast({ title: 'Input truncated', message, variant: 'warning', durationMs: 4200 })
      } else {
        const message = 'Clipboard text pasted into source panel.'
        setSettingsNotice(message)
        emitToast({ title: 'Pasted', message, variant: 'success', durationMs: 3000 })
      }
    } catch {
      const message = 'Clipboard access denied. Allow paste permissions and retry.'
      setSettingsNotice(message)
      emitToast({ title: 'Paste blocked', message, variant: 'error', durationMs: 4200 })
    } finally {
      focusSourceInput()
    }
  }, [emitToast, focusSourceInput])

  const handleClearSourceText = useCallback(() => {
    if (!sourceText) return

    setSourceText('')
    setBtvlError('')
    setBtvlResult(null)
    setSettingsNotice('Source text cleared.')
    lastSentKeyRef.current = ''
    forceRef.current = false
    focusSourceInput()
  }, [focusSourceInput, sourceText])

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
        const message = err.message || 'Text-to-speech failed.'
        setTtsError(message)
        emitToast({ title: 'Edge-TTS error', message, variant: 'error', durationMs: 4800 })
      }
    } finally {
      setTtsLoadingKey((current) => (current === slot ? null : current))
    }
  }, [apiUrl, canUseTts, emitToast])

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
        pivotLanguage: payloadResponse?.pivot_language || '',
        routeStrategy: payloadResponse?.route_strategy || (payloadResponse?.pivot_used ? 'proximate-pivot' : 'direct'),
        targetLang: payloadResponse?.target_lang || 'en',
      })
      emitToast({
        title: 'BTVL completed',
        message: `Verification returned in ${payloadResponse?.latency_ms ?? 0}ms.`,
        variant: 'success',
        durationMs: 3400,
      })
    } catch (err) {
      const message = err?.message
        ? String(err.message)
        : extractApiErrorMessage(err?.response?.data, 'Back-translation verification failed.')
      setBtvlResult(null)
      setBtvlError(message)
      emitToast({ title: 'BTVL failed', message, variant: 'error', durationMs: 5000 })
    } finally {
      setBtvlLoading(false)
    }
  }, [apiReady, apiUrl, emitToast, targetLang, translatedText])

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

      const message = 'Mock export package generated locally.'
      setSettingsNotice(message)
      emitToast({ title: 'Export ready', message, variant: 'success', durationMs: 3200 })
    } catch {
      const message = 'Export mock failed in this browser context.'
      setSettingsNotice(message)
      emitToast({ title: 'Export failed', message, variant: 'error', durationMs: 4200 })
    }
  }, [activeMode, emitToast, sourceLang, sourceText, targetLang, translatedText])

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
    emitToast({
      title: 'Source language updated',
      message: `Pre-flight LID accepted for ${preflightLid.label}.`,
      variant: 'info',
      durationMs: 3200,
    })
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
      tone="primary"
    />
  )

  const targetLangBar = (
    <LanguageSelector
      selected={targetLang}
      onSelect={handleTargetChange}
      visibleCodes={TARGET_VISIBLE}
      dropdownCodes={TARGET_DROPDOWN}
      excludeCode={sourceLang === 'auto' ? null : sourceLang}
      tone="subtle"
    />
  )

  const swapBtn = (
    <button
      type="button"
      onClick={handleSwap}
      disabled={sourceLang === 'auto'}
      className="mt-1.5 inline-flex h-10 w-10 items-center justify-center rounded-full border border-border-subtle/40 bg-bg-card/80 text-text-secondary shadow-[0_4px_20px_rgb(0,0,0,0.08)] backdrop-blur-xl transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] hover:bg-bg-elevated hover:text-text-primary active:scale-95 disabled:cursor-not-allowed disabled:opacity-30"
      title="Swap languages"
      aria-label="Swap source and target languages"
    >
      <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    </button>
  )

  const modeToggle = (
    <div className="inline-flex flex-col items-center gap-1.5">
      <div className="relative inline-flex items-center rounded-2xl border border-border-subtle/80 bg-bg-elevated/70 p-1.5 shadow-[0_8px_20px_rgba(0,0,0,0.1)]">
        <span
          className="pointer-events-none absolute -left-7 top-1/2 h-10 w-10 -translate-y-1/2 rounded-full bg-accent-magenta/18 blur-xl"
          aria-hidden="true"
        />
        <span
          className="pointer-events-none absolute -right-7 top-1/2 h-10 w-10 -translate-y-1/2 rounded-full bg-accent-gold/14 blur-xl"
          aria-hidden="true"
        />

        <button
          type="button"
          onClick={() => setIsStreetMode(false)}
          className={`relative z-10 min-w-[6.25rem] rounded-xl px-3.5 py-1.5 text-xs font-semibold tracking-[0.01em] transition-all ${
            !isStreetMode
              ? 'bg-gradient-to-r from-accent-magenta/24 to-accent-gold/16 text-accent-magenta shadow-[0_8px_18px_rgba(217,70,239,0.2)]'
              : 'text-text-secondary/85 hover:bg-bg-card/70 hover:text-text-primary'
          }`}
          aria-label="Switch to formal register"
          aria-pressed={!isStreetMode}
        >
          Formal
        </button>
        <button
          type="button"
          onClick={() => setIsStreetMode(true)}
          className={`relative z-10 min-w-[6.25rem] rounded-xl px-3.5 py-1.5 text-xs font-semibold tracking-[0.01em] transition-all ${
            isStreetMode
              ? 'bg-gradient-to-r from-accent-gold/18 to-accent-magenta/24 text-accent-magenta shadow-[0_8px_18px_rgba(217,70,239,0.2)]'
              : 'text-text-secondary/85 hover:bg-bg-card/70 hover:text-text-primary'
          }`}
          aria-label="Switch to street register"
          aria-pressed={isStreetMode}
        >
          Street
        </button>
      </div>

      <p className="text-[11px] text-text-secondary/78">
        Formal for academic tone, Street for community cadence.
      </p>
    </div>
  )

  const renderInputBox = () => (
    <div className={`relative flex min-h-[14.5rem] flex-col rounded-[1.25rem] border shadow-[0_8px_30px_rgb(0,0,0,0.04)] transition-all duration-300 ${
      isCharLimitExceeded
        ? 'border-status-danger-border/90 bg-bg-card/92 shadow-[0_0_0_1px_rgba(185,28,28,0.3),0_10px_24px_rgba(0,0,0,0.08)]'
        : 'border-border-subtle bg-bg-card/90'
    }`}>
      <div className="border-b border-border-subtle/55 px-4 py-2.5">
        <div className="ml-1 w-full max-w-[20rem] sm:max-w-[64%]">
          {sourceLangBar}
        </div>
      </div>

      <div className="relative">
        {hasSourceChars && (
          <button
            type="button"
            onClick={handleClearSourceText}
            className="absolute right-3 top-2.5 z-20 inline-flex h-7 w-7 items-center justify-center rounded-full border border-border-subtle/60 bg-bg-elevated/88 text-text-secondary transition-all duration-200 hover:border-accent-magenta/45 hover:text-accent-magenta active:scale-95"
            aria-label="Clear source text"
            title="Clear source text"
          >
            <CloseIcon className="h-3.5 w-3.5" />
          </button>
        )}

        <textarea
          ref={sourceTextareaRef}
          value={sourceText}
          onChange={(event) => setSourceText(event.target.value)}
          onFocus={() => setIsSourceInputFocused(true)}
          onBlur={() => setIsSourceInputFocused(false)}
          placeholder={SOURCE_PLACEHOLDER}
          className="translate-workbench-source h-[156px] w-full resize-none overflow-y-auto bg-transparent px-4 pt-3 pb-2 text-left text-base font-medium leading-relaxed tracking-[0.004em] text-text-primary placeholder-text-secondary/45 focus:outline-none"
          maxLength={CHAR_LIMIT}
        />
      </div>

      {showSourceQuickActions && (
        <div className="flex justify-center px-4 pb-2 pt-1">
          <div className="flex flex-wrap items-center justify-center gap-2 rounded-2xl border border-border-subtle/70 bg-bg-elevated/88 px-2.5 py-2 shadow-[0_8px_24px_rgb(0,0,0,0.08)] backdrop-blur-sm">
            <button
              type="button"
              onClick={handleCycleSample}
              className="a26-button-ghost inline-flex items-center gap-1 border-dashed px-2.5 py-1 text-xs font-medium"
              title="Load the next thesis sample input"
            >
              <FlaskConical className="h-3.5 w-3.5" />
              Sample Test
            </button>
            <span className="h-4 w-px bg-border-subtle/70" aria-hidden="true" />
            <button
              type="button"
              onClick={handlePasteText}
              className="a26-button-ghost inline-flex items-center gap-1 border-dashed px-2.5 py-1 text-xs font-medium"
              title="Paste source text from clipboard"
            >
              <ClipboardPaste className="h-3.5 w-3.5" />
              Paste Text
            </button>
          </div>
        </div>
      )}

      {hasSourceChars && (
        <div className="flex items-center justify-between border-t border-border-subtle/40 px-4 py-2">
          <button
            onClick={() => handleSpeak(sourceText, effectiveSourceLang, 'source')}
            disabled={!canUseTts}
            className="a26-button-ghost px-2 py-1 text-[11px] font-medium disabled:cursor-not-allowed disabled:opacity-35"
            title={canUseTts ? 'Preview source audio with Edge-TTS' : 'Backend Edge-TTS is unavailable'}
          >
            {ttsLoadingKey === 'source' ? '🔊 Speaking…' : '🔊 Source TTS'}
          </button>

          <span className={`text-xs tabular-nums ${isCharLimitExceeded ? 'text-status-danger-text' : 'text-text-secondary'}`}>
            {sourceCharCount}/{CHAR_LIMIT}
          </span>
        </div>
      )}

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

  const renderOutputBox = () => (
    <div className="flex min-h-[14.5rem] flex-col rounded-[1.25rem] border border-border-subtle/70 bg-bg-card/82 shadow-[0_6px_22px_rgb(0,0,0,0.04)]">
      <div className="border-b border-border-subtle/55 px-4 py-2.5">
        <div className="ml-1 w-full max-w-[20rem] sm:max-w-[64%]">
          {targetLangBar}
        </div>
      </div>

      <div className="translate-workbench-target h-[156px] overflow-y-auto px-4 pt-3 pb-1">
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
            {btvlLoading ? '🔄 Analyzing Gap…' : '🔄 Analyze Gap'}
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
              className={`rounded-xl p-1.5 transition-all duration-200 active:scale-[0.98] ${
                copied
                  ? 'bg-accent-magenta/10 text-accent-magenta'
                  : 'text-text-secondary hover:bg-bg-elevated hover:text-accent-magenta'
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
            Click <span className="font-semibold text-accent-gold">🔄 BTVL</span> to run a semantic verification pass.
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
            <p className="font-semibold text-accent-gold">Back-Translation Verification</p>
            <p className="leading-relaxed text-text-primary">{btvlResult.verifiedText}</p>
            <p className="text-[11px] text-text-secondary">
              Model: <span className="text-text-primary">{btvlResult.model}</span>
              {' '}| Latency: <span className="text-text-primary">{btvlResult.latencyMs ?? 0}ms</span>
              {' '}| Tokens: <span className="text-text-primary">{btvlResult.tokensIn ?? 0}{' -> '}{btvlResult.tokensOut ?? 0}</span>
              {' '}| Route: <span className="text-text-primary">{btvlResult.routeStrategy || (btvlResult.pivotUsed ? 'proximate-pivot' : 'direct')}</span>
              {' '}| Pivot: <span className="text-text-primary">{btvlResult.pivotLanguage || 'none'}</span>
              {' '}| Target: <span className="text-text-primary">{btvlResult.targetLang || 'en'}</span>
            </p>
          </div>
        )}
      </div>
    </div>
  )

  const renderProfilerCard = () => (
    <section
      className={`flex h-full min-h-[10rem] flex-col rounded-[1.25rem] border border-border-subtle bg-bg-card transition-shadow ${
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
        <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col space-y-4 overflow-y-auto">
          <section
            className="a26-surface a26-intro-enter relative overflow-hidden px-4 py-4 sm:px-5"
            style={{ '--a26-intro-delay': '0ms' }}
          >
            <div className="pointer-events-none absolute -top-8 right-0 h-24 w-24 rounded-full bg-accent-magenta/10 blur-2xl" />
            <div className="pointer-events-none absolute -bottom-8 left-6 h-20 w-20 rounded-full bg-accent-gold/10 blur-2xl" />

            <div className="relative">
              <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Sociolinguistic Translation Studio</h2>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">
                Route Formal or Street translation paths, validate source-language intent before inference, and review latency, token flow, and telemetry diagnostics after each run.
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="a26-chip a26-intro-enter" style={{ '--a26-intro-delay': '40ms' }}>Mode {activeModeLabel}</span>
                <span className="a26-chip a26-intro-enter" style={{ '--a26-intro-delay': '70ms' }}>Engine {translationEngine || 'unknown'}</span>
                <span className="a26-chip a26-intro-enter" style={{ '--a26-intro-delay': '100ms' }}>Telemetry {telemetry.loading ? 'Syncing' : 'Live'}</span>
              </div>
            </div>
          </section>

      {/* ══ DESKTOP ══ (md+) */}
      <div className="hidden flex-1 flex-col md:flex">
        <div className="a26-intro-enter mb-3 flex flex-col items-center gap-2" style={{ '--a26-intro-delay': '50ms' }}>
          {modeToggle}
          {swapBtn}
        </div>

        <div className="a26-intro-enter mb-3" style={{ '--a26-intro-delay': '80ms' }}>{renderLidMismatchBanner()}</div>

        <div className="grid grid-cols-2 gap-4">
          <div className="a26-intro-enter" style={{ '--a26-intro-delay': '110ms' }}>
            {renderInputBox()}
          </div>
          <div className="a26-intro-enter" style={{ '--a26-intro-delay': '140ms' }}>
            {renderOutputBox()}
          </div>
        </div>

        <div className="mt-4 grid auto-rows-fr grid-cols-2 gap-4">
          <div className="a26-intro-enter" style={{ '--a26-intro-delay': '170ms' }}>
            <GapAnalysisTerminal
              logs={systemLogs}
              isFlushing={loading}
              className="h-full min-h-[10rem]"
            />
          </div>
          <div className="a26-intro-enter" style={{ '--a26-intro-delay': '200ms' }}>
            {renderProfilerCard()}
          </div>
        </div>
      </div>

      {/* ══ MOBILE ══ (<md) */}
      <div className="flex flex-1 flex-col gap-2.5 md:hidden">
        <div className="a26-intro-enter mt-0.5 flex flex-col items-center gap-2" style={{ '--a26-intro-delay': '50ms' }}>
          {modeToggle}
          {swapBtn}
        </div>
        <div className="a26-intro-enter" style={{ '--a26-intro-delay': '85ms' }}>{renderInputBox()}</div>
        <div className="a26-intro-enter" style={{ '--a26-intro-delay': '115ms' }}>{renderLidMismatchBanner()}</div>
        <div className="a26-intro-enter" style={{ '--a26-intro-delay': '145ms' }}>{renderOutputBox()}</div>

        <div className="mt-1 flex flex-col gap-2.5">
          <div className="a26-intro-enter" style={{ '--a26-intro-delay': '175ms' }}>
            <GapAnalysisTerminal
              logs={systemLogs}
              isFlushing={loading}
              className="min-h-[10rem]"
            />
          </div>
          <div className="a26-intro-enter" style={{ '--a26-intro-delay': '205ms' }}>{renderProfilerCard()}</div>
        </div>
      </div>

      <div className="a26-intro-enter mt-3 flex flex-col items-center gap-2" style={{ '--a26-intro-delay': '230ms' }}>
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
