import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
  Activity,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ClipboardCopy,
  Download,
  Filter,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Trash2,
  TriangleAlert,
} from 'lucide-react'

const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'success', label: 'Success' },
  { value: 'error', label: 'Error' },
  { value: 'timeout', label: 'Timeout' },
]

const SOURCE_LANGUAGE_OPTIONS = [
  { value: 'all', label: 'All Sources' },
  { value: 'auto', label: 'Auto' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'tl', label: 'Tagalog' },
  { value: 'cbk', label: 'Chavacano' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
]

const TARGET_LANGUAGE_OPTIONS = [
  { value: 'all', label: 'All Targets' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'tl', label: 'Tagalog' },
  { value: 'cbk', label: 'Chavacano' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
]

const MAX_QUERY_LENGTH = 64
const POLL_INTERVAL_MS = 20000
const LOG_FETCH_LIMIT = 200
const EXPORT_FETCH_LIMIT = 200
const ROWS_PER_PAGE = 20
const SUPPRESSED_LOGS_STORAGE_KEY = 'puente-activity-logs-suppressed-v1'

const PIVOT_LANGUAGE_LABELS = {
  tl: 'Tagalog',
  ceb: 'Cebuano/Bisaya',
  es: 'Spanish',
}

function sanitizeQuery(value) {
  return String(value || '')
    .replace(/[<>{}`$]/g, '')
    .slice(0, MAX_QUERY_LENGTH)
}

function formatTime(isoValue) {
  if (!isoValue) return '-'

  try {
    return new Date(isoValue).toLocaleString()
  } catch {
    return '-'
  }
}

function formatLatency(latencyMs) {
  if (!Number.isFinite(latencyMs) || latencyMs < 0) {
    return '--'
  }
  return `${Math.round(latencyMs)} ms`
}

function normalizeRouteConfidence(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return null
  }

  if (numeric >= 0 && numeric <= 1) {
    return numeric
  }

  if (numeric > 1 && numeric <= 100) {
    return numeric / 100
  }

  return Math.max(0, Math.min(1, numeric))
}

function formatRouteConfidence(value) {
  const normalized = normalizeRouteConfidence(value)
  if (normalized === null) {
    return '--'
  }

  return `${Math.round(normalized * 100)}%`
}

function routeConfidenceToneClass(value) {
  const normalized = normalizeRouteConfidence(value)
  if (normalized === null) {
    return 'border-border-subtle/70 bg-bg-elevated/70 text-text-secondary'
  }

  if (normalized >= 0.75) {
    return 'border-status-success-border/70 bg-status-success-bg/70 text-status-success-text'
  }

  if (normalized >= 0.45) {
    return 'border-status-warning-border/70 bg-status-warning-bg/70 text-status-warning-text'
  }

  return 'border-status-danger-border/70 bg-status-danger-bg/70 text-status-danger-text'
}

function routeConfidenceBarClass(value) {
  const normalized = normalizeRouteConfidence(value)
  if (normalized === null) {
    return 'bg-border-subtle/70'
  }

  if (normalized >= 0.75) {
    return 'bg-status-success-text'
  }

  if (normalized >= 0.45) {
    return 'bg-status-warning-text'
  }

  return 'bg-status-danger-text'
}

function toFiniteNumber(value, fallback = 0) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function hashText(value) {
  const text = String(value ?? '')
  let hash = 0
  for (let index = 0; index < text.length; index += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0
  }
  return Math.abs(hash)
}

function computeBtvlProxy(row) {
  // BTVL proxy is deterministic and mock-based for observer visualization.
  if (row?.status !== 'success' || !String(row?.output_text || '').trim()) {
    return '--'
  }

  const tokensIn = toFiniteNumber(row?.input_tokens)
  const tokensOut = toFiniteNumber(row?.output_tokens)
  const latency = toFiniteNumber(row?.latency_ms)
  const seed = hashText(`${row?.id}-${tokensIn}-${tokensOut}-${latency}`)

  let score = 82 + (seed % 14)
  if (row?.pivot_used) score += 2
  if (row?.wiki_voz_triggered) score += 1
  if (latency > 1200) score -= 3

  score = Math.max(70, Math.min(99, score))
  return `${score}%`
}

function computeMockVramSpike(row) {
  const latency = toFiniteNumber(row?.latency_ms)
  const tokens = toFiniteNumber(row?.input_tokens) + toFiniteNumber(row?.output_tokens)
  const base = 0.14 + tokens * 0.006 + latency * 0.00022 + (row?.pivot_used ? 0.08 : 0)
  const bounded = Math.max(0.12, Math.min(2.8, base))
  return `${bounded.toFixed(2)} GB`
}

function extractPivotCodeFromModelName(modelName) {
  const raw = String(modelName || '').toLowerCase()
  const matched = raw.match(/\+pivot-([a-z]{2,3})\b/)
  return matched?.[1] || ''
}

function resolveRouteStrategy(row) {
  const explicit = String(row?.route_strategy || '').trim()
  if (explicit) {
    return explicit
  }

  if (row?.model_name === 'tm-cache') {
    return 'tm-cache'
  }

  if (row?.model_name === 'passthrough') {
    return 'passthrough'
  }

  return row?.pivot_used ? 'proximate-pivot' : 'direct'
}

function resolvePivotLanguage(row) {
  if (!row?.pivot_used) {
    return 'Direct route (no pivot)'
  }

  const explicitCode = String(row?.pivot_language || '').trim().toLowerCase()
  const inferredCode = extractPivotCodeFromModelName(row?.model_name)
  const code = explicitCode || inferredCode

  if (!code) {
    return 'Proximate pivot (unspecified)'
  }

  return `${PIVOT_LANGUAGE_LABELS[code] || code.toUpperCase()} (${code})`
}

function isLocalModelMissingLog(row) {
  const message = String(row?.error_message || '').toLowerCase()
  const model = String(row?.model_name || '').toLowerCase()

  if (row?.status !== 'error') {
    return false
  }

  return (
    model.includes('offline-model-missing')
    || message.includes('local nllb model is unavailable')
    || message.includes('ml_models/nllb-200-distilled-600m')
    || message.includes('offline defense mode')
  )
}

function buildInterventionTags(row) {
  const tags = []

  if (row?.wiki_voz_triggered) {
    tags.push('False Cognate Avoided')
    if (row?.wiki_voz_term) {
      tags.push(`Wiki-Voz: ${row.wiki_voz_term}`)
    }
  }

  if (row?.mode === 'formal') {
    tags.push('Honorific Register Preserved')
  }

  if (row?.mode === 'street') {
    tags.push('Street Register Alignment')
  }

  if (row?.pivot_used) {
    tags.push('Proximate Pivot Stabilization')
  }

  if (resolveRouteStrategy(row) === 'tm-cache') {
    tags.push('TM Cache Replay')
  }

  return [...new Set(tags)]
}

function findOptionLabel(options, value, fallbackLabel = 'All') {
  const matched = options.find((option) => option.value === value)
  return matched?.label || fallbackLabel
}

function escapeCsvCell(value) {
  const raw = String(value ?? '')
  if (/[,"\n]/.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`
  }
  return raw
}

function buildLogsCsv(rows) {
  const headers = [
    'id',
    'timestamp',
    'source_lang',
    'target_lang',
    'mode',
    'status',
    'latency_ms',
    'tokens_in',
    'tokens_out',
    'btvl_proxy',
    'route_strategy',
    'route_confidence',
    'pivot_used',
    'pivot_language',
    'vram_spike',
    'model_name',
    'wiki_voz_triggered',
    'wiki_voz_term',
    'error_message',
    'input_text',
    'output_text',
  ]

  const lines = rows.map((row) => {
    const values = [
      row?.id,
      row?.created_at,
      row?.source_lang,
      row?.target_lang,
      row?.mode,
      row?.status,
      toFiniteNumber(row?.latency_ms).toFixed(1),
      toFiniteNumber(row?.input_tokens),
      toFiniteNumber(row?.output_tokens),
      computeBtvlProxy(row),
      resolveRouteStrategy(row),
      formatRouteConfidence(row?.route_confidence),
      row?.pivot_used ? 'true' : 'false',
      resolvePivotLanguage(row),
      computeMockVramSpike(row),
      row?.model_name,
      row?.wiki_voz_triggered ? 'true' : 'false',
      row?.wiki_voz_term,
      row?.error_message,
      row?.input_text,
      row?.output_text,
    ]

    return values.map(escapeCsvCell).join(',')
  })

  return [headers.join(','), ...lines].join('\n')
}

function buildLogPayload(row) {
  return {
    id: row?.id,
    timestamp: row?.created_at,
    language_pair: `${row?.source_lang || '-'} -> ${row?.target_lang || '-'}`,
    mode: row?.mode,
    status: row?.status,
    model_name: row?.model_name,
    latency_ms: toFiniteNumber(row?.latency_ms),
    tokens: {
      input: toFiniteNumber(row?.input_tokens),
      output: toFiniteNumber(row?.output_tokens),
    },
    btvl_proxy: computeBtvlProxy(row),
    metadata: {
      chars: toFiniteNumber(row?.input_chars),
      route_strategy: resolveRouteStrategy(row),
      route_confidence: formatRouteConfidence(row?.route_confidence),
      pivot_used: Boolean(row?.pivot_used),
      pivot_language: resolvePivotLanguage(row),
      vram_spike: computeMockVramSpike(row),
      interventions: buildInterventionTags(row),
      wiki_voz_triggered: Boolean(row?.wiki_voz_triggered),
      wiki_voz_term: row?.wiki_voz_term || '',
    },
    error_message: row?.error_message || '',
    input_text: row?.input_text || '',
    output_text: row?.output_text || '',
  }
}

function buildPaginationItems(totalPages, currentPage) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const pages = [1]
  const windowStart = Math.max(2, currentPage - 1)
  const windowEnd = Math.min(totalPages - 1, currentPage + 1)

  if (windowStart > 2) {
    pages.push('ellipsis-start')
  }

  for (let page = windowStart; page <= windowEnd; page += 1) {
    pages.push(page)
  }

  if (windowEnd < totalPages - 1) {
    pages.push('ellipsis-end')
  }

  pages.push(totalPages)
  return pages
}

function statusBadgeClass(status) {
  if (status === 'success') {
    return 'border-status-success-border/70 bg-status-success-bg/70 text-status-success-text'
  }

  if (status === 'error') {
    return 'border-status-danger-border/70 bg-status-danger-bg/70 text-status-danger-text'
  }

  if (status === 'timeout') {
    return 'border-status-warning-border/70 bg-status-warning-bg/70 text-status-warning-text'
  }

  return 'border-border-subtle/70 bg-bg-elevated/70 text-text-secondary'
}

export default function ActivityLogsScreen({ apiUrl, backendUp, notify }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [targetFilter, setTargetFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [totalCount, setTotalCount] = useState(0)
  const [expandedLogId, setExpandedLogId] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [lastSyncedAt, setLastSyncedAt] = useState('')
  const [suppressedLogIds, setSuppressedLogIds] = useState(() => {
    if (typeof window === 'undefined') {
      return new Set()
    }

    try {
      const raw = window.localStorage.getItem(SUPPRESSED_LOGS_STORAGE_KEY)
      const parsed = raw ? JSON.parse(raw) : []
      return new Set(Array.isArray(parsed) ? parsed.map(String) : [])
    } catch {
      return new Set()
    }
  })

  const emitToast = useCallback((payload) => {
    if (typeof notify === 'function') {
      notify(payload)
    }
  }, [notify])

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim())
    }, 280)

    return () => clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, sourceFilter, targetFilter, debouncedQuery])

  useEffect(() => {
    if (typeof window === 'undefined') return

    try {
      window.localStorage.setItem(
        SUPPRESSED_LOGS_STORAGE_KEY,
        JSON.stringify([...suppressedLogIds]),
      )
    } catch {
      // Local persistence is best-effort for deleted mock rows.
    }
  }, [suppressedLogIds])

  const fetchLogs = useCallback(async ({ silent = false } = {}) => {
    if (!backendUp) {
      const message = 'Backend is offline. Activity logs are unavailable until backend reconnects.'
      setError(message)
      if (!silent) {
        emitToast({
          title: 'Observer unavailable',
          message,
          variant: 'warning',
          durationMs: 4200,
        })
      }
      if (!silent) {
        setLoading(false)
      }
      return
    }

    if (silent) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    setError('')

    try {
      const params = {
        limit: LOG_FETCH_LIMIT,
      }

      if (statusFilter !== 'all') {
        params.status = statusFilter
      }

      if (sourceFilter !== 'all') {
        params.source_lang = sourceFilter
      }

      if (targetFilter !== 'all') {
        params.target_lang = targetFilter
      }

      if (debouncedQuery) {
        params.q = debouncedQuery
      }

      const { data } = await axios.get(`${apiUrl}/logs/`, {
        params,
        timeout: 10000,
      })

      const nextRows = data?.results || []
      setLogs(nextRows)
      setTotalCount(Number(data?.count || nextRows.length || 0))

      setLastSyncedAt(new Date().toISOString())
    } catch {
      const message = 'Failed to load activity logs from backend observer endpoint.'
      setError(message)
      if (!silent) {
        emitToast({
          title: 'Observer request failed',
          message,
          variant: 'error',
          durationMs: 4600,
        })
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [apiUrl, backendUp, debouncedQuery, emitToast, sourceFilter, statusFilter, targetFilter])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  useEffect(() => {
    if (!backendUp) return undefined

    const interval = setInterval(() => {
      fetchLogs({ silent: true })
    }, POLL_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [backendUp, fetchLogs])

  const visibleLogs = useMemo(
    () => logs.filter((row) => !suppressedLogIds.has(String(row.id))),
    [logs, suppressedLogIds],
  )

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(visibleLogs.length / ROWS_PER_PAGE)),
    [visibleLogs.length],
  )

  useEffect(() => {
    setCurrentPage((previous) => Math.min(previous, totalPages))
  }, [totalPages])

  const pageStartIndex = (currentPage - 1) * ROWS_PER_PAGE

  const pagedLogs = useMemo(
    () => visibleLogs.slice(pageStartIndex, pageStartIndex + ROWS_PER_PAGE),
    [pageStartIndex, visibleLogs],
  )

  const paginationItems = useMemo(
    () => buildPaginationItems(totalPages, currentPage),
    [currentPage, totalPages],
  )

  useEffect(() => {
    if (!expandedLogId) return

    const stillVisible = pagedLogs.some((row) => String(row.id) === String(expandedLogId))
    if (!stillVisible) {
      setExpandedLogId(null)
    }
  }, [expandedLogId, pagedLogs])

  const summary = useMemo(() => {
    return visibleLogs.reduce((acc, row) => {
      acc.total += 1
      if (row.status === 'success') acc.success += 1
      if (row.status === 'error') acc.error += 1
      if (row.status === 'timeout') acc.timeout += 1
      return acc
    }, { total: 0, success: 0, error: 0, timeout: 0 })
  }, [visibleLogs])

  const pageRangeStart = visibleLogs.length === 0 ? 0 : pageStartIndex + 1
  const pageRangeEnd = Math.min(pageStartIndex + ROWS_PER_PAGE, visibleLogs.length)

  const statusFilterLabel = useMemo(
    () => findOptionLabel(STATUS_OPTIONS, statusFilter, 'All Statuses'),
    [statusFilter],
  )

  const sourceFilterLabel = useMemo(
    () => findOptionLabel(SOURCE_LANGUAGE_OPTIONS, sourceFilter, 'All Sources'),
    [sourceFilter],
  )

  const targetFilterLabel = useMemo(
    () => findOptionLabel(TARGET_LANGUAGE_OPTIONS, targetFilter, 'All Targets'),
    [targetFilter],
  )

  const hasActiveFilters = (
    statusFilter !== 'all'
    || sourceFilter !== 'all'
    || targetFilter !== 'all'
    || Boolean(searchQuery.trim())
  )

  const handleResetFilters = useCallback(() => {
    setStatusFilter('all')
    setSourceFilter('all')
    setTargetFilter('all')
    setSearchQuery('')
    setDebouncedQuery('')
    setCurrentPage(1)
  }, [])

  const handleCopyPayload = useCallback(async (row) => {
    const payload = buildLogPayload(row)
    const clipboardText = JSON.stringify(payload, null, 2)

    if (!navigator?.clipboard?.writeText) {
      emitToast({
        title: 'Copy unavailable',
        message: 'Clipboard API is unavailable in this browser context.',
        variant: 'warning',
        durationMs: 3800,
      })
      return
    }

    try {
      await navigator.clipboard.writeText(clipboardText)
      emitToast({
        title: 'Payload copied',
        message: `Log ${row.id} JSON payload copied to clipboard.`,
        variant: 'success',
        durationMs: 2600,
      })
    } catch {
      emitToast({
        title: 'Copy failed',
        message: 'Could not write JSON payload to clipboard.',
        variant: 'error',
        durationMs: 4200,
      })
    }
  }, [emitToast])

  const handleDeleteLog = useCallback((row) => {
    const rowId = String(row?.id)
    setSuppressedLogIds((previous) => {
      const next = new Set(previous)
      next.add(rowId)
      return next
    })

    setExpandedLogId((previous) => (
      String(previous) === rowId ? null : previous
    ))

    emitToast({
      title: 'Log hidden',
      message: `Log ${rowId} removed from local flight-recorder view.`,
      variant: 'info',
      durationMs: 2800,
    })
  }, [emitToast])

  const handleExportAllLogs = useCallback(async () => {
    setExporting(true)

    let rowsForExport = []

    try {
      const { data } = await axios.get(`${apiUrl}/logs/`, {
        params: { limit: EXPORT_FETCH_LIMIT },
        timeout: 12000,
      })

      rowsForExport = (data?.results || [])
        .filter((row) => !suppressedLogIds.has(String(row.id)))
    } catch {
      // Fallback to currently loaded rows if full export fetch is unavailable.
      rowsForExport = visibleLogs
    }

    if (rowsForExport.length === 0) {
      setExporting(false)
      emitToast({
        title: 'Nothing to export',
        message: 'No activity logs are available for CSV export.',
        variant: 'warning',
        durationMs: 3200,
      })
      return
    }

    const csv = buildLogsCsv(rowsForExport)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `puente-flight-recorder-${Date.now()}.csv`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)

    setExporting(false)
    emitToast({
      title: 'Export completed',
      message: `${rowsForExport.length} logs exported to CSV.`,
      variant: 'success',
      durationMs: 3000,
    })
  }, [apiUrl, emitToast, suppressedLogIds, visibleLogs])

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="a26-surface relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -right-8 top-0 h-36 w-36 rounded-full bg-accent-magenta/10 blur-3xl" />

        <div className="relative flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="a26-subtitle">Observer Agent</p>
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Flight Recorder</h2>
            <p className="mt-2 max-w-3xl text-sm text-text-secondary">
              Offline MLOps trace surface for translation outcomes, pivot routing, intervention tags, and recovery diagnostics.
            </p>
          </div>

          <div className="ml-auto flex shrink-0 items-start">
            <button
              type="button"
              onClick={() => fetchLogs()}
              className="a26-button-ghost inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold"
              title="Refresh observer logs"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <span className="a26-chip"><Activity className="h-3.5 w-3.5" /> Visible {summary.total}</span>
          <span className="rounded-full border border-status-success-border/70 bg-status-success-bg/70 px-3 py-1 text-status-success-text">
            Success {summary.success}
          </span>
          <span className="rounded-full border border-status-danger-border/70 bg-status-danger-bg/70 px-3 py-1 text-status-danger-text">
            Error {summary.error}
          </span>
          <span className="rounded-full border border-status-warning-border/70 bg-status-warning-bg/70 px-3 py-1 text-status-warning-text">
            Timeout {summary.timeout}
          </span>
          <span className="rounded-full border border-border-subtle/70 bg-bg-elevated/70 px-3 py-1 text-text-secondary">
            Total matched {Math.max(visibleLogs.length, totalCount - suppressedLogIds.size)}
          </span>
          {lastSyncedAt ? (
            <span className="rounded-full border border-border-subtle/70 bg-bg-elevated/70 px-3 py-1 text-text-secondary">
              Synced {formatTime(lastSyncedAt)}
            </span>
          ) : null}
        </div>

        <div className="mt-4 flex justify-end border-t border-border-subtle/55 pt-3">
          <button
            type="button"
            onClick={handleExportAllLogs}
            disabled={exporting}
            className="a26-button-ghost inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold disabled:opacity-55"
            title="Export all logs as CSV"
          >
            <Download className={`h-4 w-4 ${exporting ? 'animate-pulse' : ''}`} />
            Export All Logs (CSV)
          </button>
        </div>
      </header>

      <section className="a26-surface p-4 md:p-5">
        {/* Search + filters are arranged as a stylized control rail for rapid observer triage. */}
        <div className="mb-3 overflow-hidden rounded-2xl border border-border-subtle/80 bg-bg-elevated/35">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle/70 bg-bg-card/55 px-3.5 py-2.5">
            <div className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.13em] text-text-secondary">
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Query and Filter Controls
            </div>

            <button
              type="button"
              onClick={handleResetFilters}
              disabled={!hasActiveFilters}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle/70 bg-bg-elevated/65 px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-45"
            >
              <RefreshCw className="h-3 w-3" />
              Reset Filters
            </button>
          </div>

          <div className="space-y-3 p-3.5">
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.45fr)_minmax(0,0.55fr)_minmax(0,0.7fr)_minmax(0,0.7fr)]">
              <label className="space-y-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Search</span>
                <span className="relative block">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                  <input
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(sanitizeQuery(event.target.value))}
                    placeholder="Search text, wiki term, error message"
                    className="w-full rounded-xl border border-border-subtle bg-bg-card/80 py-2.5 pl-9 pr-3 text-sm text-text-primary placeholder-text-secondary/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition-all duration-300 focus:border-accent-magenta/70 focus:shadow-[0_0_0_3px_rgba(217,70,239,0.14)] focus:outline-none"
                  />
                </span>
              </label>

              <label className="space-y-1.5">
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">
                  <Filter className="h-3 w-3" />
                  Status
                </span>
                <span className="relative block">
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                    className="w-full appearance-none rounded-xl border border-border-subtle bg-bg-card/80 px-3 py-2.5 pr-9 text-sm font-semibold text-text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition-all duration-300 focus:border-accent-magenta/70 focus:shadow-[0_0_0_3px_rgba(217,70,239,0.14)] focus:outline-none"
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                </span>
              </label>

              <label className="space-y-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Source</span>
                <span className="relative block">
                  <select
                    value={sourceFilter}
                    onChange={(event) => setSourceFilter(event.target.value)}
                    className="w-full appearance-none rounded-xl border border-border-subtle bg-bg-card/80 px-3 py-2.5 pr-9 text-sm font-semibold text-text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition-all duration-300 focus:border-accent-magenta/70 focus:shadow-[0_0_0_3px_rgba(217,70,239,0.14)] focus:outline-none"
                  >
                    {SOURCE_LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                </span>
              </label>

              <label className="space-y-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Target</span>
                <span className="relative block">
                  <select
                    value={targetFilter}
                    onChange={(event) => setTargetFilter(event.target.value)}
                    className="w-full appearance-none rounded-xl border border-border-subtle bg-bg-card/80 px-3 py-2.5 pr-9 text-sm font-semibold text-text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition-all duration-300 focus:border-accent-magenta/70 focus:shadow-[0_0_0_3px_rgba(217,70,239,0.14)] focus:outline-none"
                  >
                    {TARGET_LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
                </span>
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span className="rounded-full border border-border-subtle/70 bg-bg-card/75 px-2.5 py-1 font-semibold text-text-secondary">
                Status: {statusFilterLabel}
              </span>
              <span className="rounded-full border border-border-subtle/70 bg-bg-card/75 px-2.5 py-1 font-semibold text-text-secondary">
                Source: {sourceFilterLabel}
              </span>
              <span className="rounded-full border border-border-subtle/70 bg-bg-card/75 px-2.5 py-1 font-semibold text-text-secondary">
                Target: {targetFilterLabel}
              </span>
              {debouncedQuery ? (
                <span className="rounded-full border border-accent-magenta/35 bg-accent-magenta/12 px-2.5 py-1 font-semibold text-accent-magenta">
                  Query: {debouncedQuery}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {error ? (
          <div className="mb-3 inline-flex w-full items-center gap-2 rounded-xl border border-status-warning-border/70 bg-status-warning-bg/75 px-3 py-2 text-xs text-status-warning-text">
            <TriangleAlert className="h-3.5 w-3.5" />
            {error}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-2xl border border-border-subtle/80">
          <div className="overflow-x-auto">
            <div className="max-h-[460px] overflow-y-auto">
            <table className="min-w-full divide-y divide-border-subtle text-sm">
              <thead className="sticky top-0 z-10 bg-bg-elevated/95 backdrop-blur-sm">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Timestamp</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Pair</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Mode</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Status</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Latency</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Tokens</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Model</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">BTVL Proxy</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Route Conf.</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border-subtle bg-bg-card">
                {loading ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-6 text-center text-text-secondary">Loading observer logs...</td>
                  </tr>
                ) : pagedLogs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-6 text-center text-text-secondary">
                      No logs matched the current filters.
                    </td>
                  </tr>
                ) : (
                  pagedLogs.map((row) => {
                    const expanded = expandedLogId === row.id
                    const btvlProxy = computeBtvlProxy(row)
                    const routeConfidenceValue = normalizeRouteConfidence(row.route_confidence)
                    const routeConfidenceLabel = formatRouteConfidence(row.route_confidence)
                    const localModelMissing = isLocalModelMissingLog(row)
                    const interventionTags = buildInterventionTags(row)

                    return (
                      <Fragment key={row.id}>
                        <tr
                          className="transition-colors duration-200 hover:bg-bg-elevated/55"
                          title="Expand for flight-recorder execution details"
                        >
                          <td className="px-3 py-2 text-xs text-text-secondary">
                            <button
                              type="button"
                              onClick={() => setExpandedLogId(expanded ? null : row.id)}
                              className="inline-flex items-center gap-2 rounded-lg px-1 py-1 text-left transition-colors hover:text-text-primary"
                              aria-expanded={expanded}
                              aria-label={`Toggle details for log ${row.id}`}
                            >
                              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                              <span>{formatTime(row.created_at)}</span>
                            </button>
                          </td>
                          <td className="px-3 py-2 font-semibold text-text-primary">{row.source_lang}{' -> '}{row.target_lang}</td>
                          <td className="px-3 py-2 text-text-secondary">{row.mode}</td>
                          <td className="px-3 py-2">
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(row.status)}`}>
                              {row.status}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-text-secondary">{formatLatency(Number(row.latency_ms))}</td>
                          <td className="px-3 py-2 text-text-secondary">{row.input_tokens}{' -> '}{row.output_tokens}</td>
                          <td className="max-w-[280px] px-3 py-2 text-text-secondary">
                            <p className="truncate" title={row.model_name || '--'}>{row.model_name || '--'}</p>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${btvlProxy === '--' ? 'border-border-subtle/70 bg-bg-elevated/70 text-text-secondary' : 'border-status-info-border/70 bg-status-info-bg/70 text-status-info-text'}`}>
                              {btvlProxy}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <div className="space-y-1">
                              <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${routeConfidenceToneClass(row.route_confidence)}`}>
                                {routeConfidenceLabel}
                              </span>
                              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-bg-elevated/80">
                                <div
                                  className={`h-full rounded-full transition-[width] duration-300 ${routeConfidenceBarClass(row.route_confidence)}`}
                                  style={routeConfidenceValue === null ? undefined : { width: `${Math.round(routeConfidenceValue * 100)}%` }}
                                />
                              </div>
                            </div>
                          </td>
                        </tr>

                        {expanded ? (
                          <tr className="bg-bg-elevated/35">
                            <td colSpan={9} className="px-3 py-3">
                              {/* Flight-recorder layout:
                                  Left = translation I/O payload, Right = execution metadata + interventions. */}
                              <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.3fr_0.9fr]">
                                <div className="rounded-xl border border-border-subtle/70 bg-bg-card/70 p-3">
                                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Input Text</p>
                                  <textarea
                                    readOnly
                                    value={row.input_text || ''}
                                    className="mt-1.5 min-h-[110px] w-full resize-none rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-3 py-2 text-sm leading-relaxed text-text-primary focus:outline-none"
                                  />

                                  <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Output Text</p>
                                  <textarea
                                    readOnly
                                    value={row.output_text || ''}
                                    className="mt-1.5 min-h-[110px] w-full resize-none rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-3 py-2 text-sm leading-relaxed text-text-primary focus:outline-none"
                                  />
                                </div>

                                <div className="rounded-xl border border-border-subtle/70 bg-bg-card/70 p-3">
                                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Execution Metadata</p>

                                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
                                    <div className="rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-2.5 py-2">
                                      <p className="text-text-secondary">Chars</p>
                                      <p className="mt-1 font-semibold text-text-primary">{toFiniteNumber(row.input_chars)}</p>
                                    </div>
                                    <div className="rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-2.5 py-2">
                                      <p className="text-text-secondary">Route</p>
                                      <p className="mt-1 font-semibold text-text-primary">{resolveRouteStrategy(row)}</p>
                                      <p className="mt-1 text-[11px] text-text-secondary">{resolvePivotLanguage(row)}</p>
                                    </div>
                                    <div className="rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-2.5 py-2">
                                      <p className="text-text-secondary">Route Confidence</p>
                                      <p className="mt-1 font-semibold text-text-primary">{routeConfidenceLabel}</p>
                                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-bg-card/80">
                                        <div
                                          className={`h-full rounded-full transition-[width] duration-300 ${routeConfidenceBarClass(row.route_confidence)}`}
                                          style={routeConfidenceValue === null ? undefined : { width: `${Math.round(routeConfidenceValue * 100)}%` }}
                                        />
                                      </div>
                                    </div>
                                    <div className="rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-2.5 py-2">
                                      <p className="text-text-secondary">VRAM Spike</p>
                                      <p className="mt-1 font-semibold text-text-primary">{computeMockVramSpike(row)}</p>
                                    </div>
                                    <div className="rounded-lg border border-border-subtle/60 bg-bg-elevated/50 px-2.5 py-2">
                                      <p className="text-text-secondary">BTVL Match</p>
                                      <p className="mt-1 font-semibold text-text-primary">{btvlProxy}</p>
                                    </div>
                                  </div>

                                  <div className="mt-3 rounded-lg border border-border-subtle/60 bg-bg-elevated/45 px-2.5 py-2">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Sociolinguistic Interventions</p>
                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                      {interventionTags.length > 0 ? interventionTags.map((tag) => (
                                        <span
                                          key={`${row.id}-${tag}`}
                                          className="rounded-full bg-accent-magenta/20 px-2.5 py-1 text-[11px] font-semibold text-accent-magenta"
                                        >
                                          {tag}
                                        </span>
                                      )) : (
                                        <span className="text-xs text-text-secondary">No interventions recorded.</span>
                                      )}
                                    </div>
                                  </div>

                                  {localModelMissing ? (
                                    <div className="mt-3 rounded-xl border border-status-danger-border bg-status-danger-bg/88 px-3 py-2 text-xs text-status-danger-text">
                                      <p className="font-semibold">503: Local Model Missing</p>
                                      <p className="mt-1 leading-relaxed">
                                        {row.error_message || 'Local NLLB model files are missing on this node.'}
                                      </p>
                                    </div>
                                  ) : row.error_message ? (
                                    <div className="mt-3 rounded-xl border border-status-warning-border/80 bg-status-warning-bg/88 px-3 py-2 text-xs text-status-warning-text">
                                      {row.error_message}
                                    </div>
                                  ) : null}
                                </div>
                              </div>

                              <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                                <button
                                  type="button"
                                  onClick={() => handleCopyPayload(row)}
                                  className="a26-button-ghost inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold"
                                  title="Copy expanded translation payload"
                                >
                                  <ClipboardCopy className="h-3.5 w-3.5" />
                                  Copy JSON Payload
                                </button>

                                <button
                                  type="button"
                                  onClick={() => handleDeleteLog(row)}
                                  className="inline-flex items-center gap-1.5 rounded-xl border border-status-danger-border/70 bg-status-danger-bg/70 px-3 py-1.5 text-xs font-semibold text-status-danger-text transition-colors hover:bg-status-danger-bg"
                                  title="Remove this log from local activity view"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                  Delete Log
                                </button>
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    )
                  })
                )}
              </tbody>
            </table>
            </div>

            <div className="border-t border-border-subtle/75 bg-bg-card/80 px-3 py-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-text-secondary">
                  Showing {pageRangeStart}-{pageRangeEnd} of {visibleLogs.length} logs
                  {' '}• 20 rows per page
                </p>

                <div className="inline-flex items-center gap-1 rounded-xl border border-border-subtle/70 bg-bg-elevated/45 p-1">
                  <button
                    type="button"
                    onClick={() => setCurrentPage((previous) => Math.max(1, previous - 1))}
                    disabled={currentPage === 1}
                    className="a26-button-ghost inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold disabled:opacity-40"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    Prev
                  </button>

                  {paginationItems.map((item) => {
                    if (typeof item !== 'number') {
                      return (
                        <span key={item} className="px-1.5 text-xs text-text-secondary">...</span>
                      )
                    }

                    return (
                      <button
                        key={item}
                        type="button"
                        onClick={() => setCurrentPage(item)}
                        className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${currentPage === item ? 'bg-accent-magenta/20 text-accent-magenta' : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}
                        aria-label={`Go to page ${item}`}
                      >
                        {item}
                      </button>
                    )
                  })}

                  <button
                    type="button"
                    onClick={() => setCurrentPage((previous) => Math.min(totalPages, previous + 1))}
                    disabled={currentPage === totalPages}
                    className="a26-button-ghost inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold disabled:opacity-40"
                    aria-label="Next page"
                  >
                    Next
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
