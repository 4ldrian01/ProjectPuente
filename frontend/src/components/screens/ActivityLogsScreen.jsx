/**
 * ActivityLogsScreen.jsx — Observer and flight-recorder interface.
 * Summary: Displays translation logs, filtering controls, payload drill-down, and CSV export actions.
 */

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import {
  buildInterventionTags,
  buildLogsCsv,
  buildLogPayload,
  buildPaginationItems,
  computeBtvlProxy,
  computeMockVramSpike,
  EXPORT_FETCH_LIMIT,
  findOptionLabel,
  formatLatency,
  formatRouteConfidence,
  formatTime,
  isLocalModelMissingLog,
  LOG_FETCH_LIMIT,
  normalizeRouteConfidence,
  POLL_INTERVAL_MS,
  resolvePivotLanguage,
  resolveRouteStrategy,
  routeConfidenceBarClass,
  routeConfidenceToneClass,
  ROWS_PER_PAGE,
  sanitizeQuery,
  SOURCE_LANGUAGE_OPTIONS,
  STATUS_OPTIONS,
  statusBadgeClass,
  SUPPRESSED_LOGS_STORAGE_KEY,
  TARGET_LANGUAGE_OPTIONS,
  toFiniteNumber,
} from '../../lib/activityLogsUtils'

export default function ActivityLogsScreen({ apiUrl, backendUp, notify, isActive = true }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [targetFilter, setTargetFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const debouncedQuery = useDebouncedValue(searchQuery.trim(), 280)
  const [totalCount, setTotalCount] = useState(0)
  const [expandedLogId, setExpandedLogId] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [lastSyncedAt, setLastSyncedAt] = useState('')
  const [isDocumentVisible, setIsDocumentVisible] = useState(
    typeof document === 'undefined' ? true : document.visibilityState === 'visible',
  )
  const requestVersionRef = useRef(0)
  const inFlightControllerRef = useRef(null)
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
    const handleVisibilityChange = () => {
      const visible = document.visibilityState === 'visible'
      setIsDocumentVisible(visible)

      if (visible && isActive && backendUp) {
        fetchLogs({ silent: true })
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [backendUp, fetchLogs, isActive])

  useEffect(() => {
    return () => {
      if (inFlightControllerRef.current) {
        inFlightControllerRef.current.abort()
      }
    }
  }, [])

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
    if (!isActive) {
      if (!silent) {
        setLoading(false)
      }
      setRefreshing(false)
      return
    }

    if (!isDocumentVisible && silent) {
      return
    }

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

    if (inFlightControllerRef.current) {
      inFlightControllerRef.current.abort()
    }

    const controller = new AbortController()
    inFlightControllerRef.current = controller
    const requestVersion = requestVersionRef.current + 1
    requestVersionRef.current = requestVersion

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
        signal: controller.signal,
      })

      if (requestVersion !== requestVersionRef.current) {
        return
      }

      const nextRows = data?.results || []
      setLogs(nextRows)
      setTotalCount(Number(data?.count || nextRows.length || 0))

      setLastSyncedAt(new Date().toISOString())
    } catch (errorResponse) {
      if (errorResponse?.code === 'ERR_CANCELED') {
        return
      }

      if (requestVersion !== requestVersionRef.current) {
        return
      }

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
      if (inFlightControllerRef.current === controller) {
        inFlightControllerRef.current = null
      }

      if (requestVersion === requestVersionRef.current) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [apiUrl, backendUp, debouncedQuery, emitToast, isActive, isDocumentVisible, sourceFilter, statusFilter, targetFilter])

  useEffect(() => {
    if (!isActive) {
      return
    }

    fetchLogs()
  }, [fetchLogs, isActive])

  useEffect(() => {
    if (!backendUp || !isActive || !isDocumentVisible) return undefined

    const interval = setInterval(() => {
      fetchLogs({ silent: true })
    }, POLL_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [backendUp, fetchLogs, isActive, isDocumentVisible])

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
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Activity Logs</h2>
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
          <span className="a26-chip"><Activity className="h-[0.875rem] w-[0.875rem]" /> Visible {summary.total}</span>
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
            <Download className={`h-4 w-4 ${exporting ? 'a26-animate-pulse' : ''}`} />
            Export All Logs (CSV)
          </button>
        </div>
      </header>

      <section className="a26-surface p-4 md:p-5">
        {/* Search + filters are arranged as a stylized control rail for rapid observer triage. */}
        <div className="mb-3 overflow-hidden rounded-2xl border border-border-subtle/80 bg-bg-elevated/35">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle/70 bg-bg-card/55 px-3.5 py-2.5">
            <div className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.13em] text-text-secondary">
              <SlidersHorizontal className="h-[0.875rem] w-[0.875rem]" />
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
                <span className="a26-select-wrap block">
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
                <span className="a26-select-wrap block">
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                    className="a26-select"
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="a26-select-icon" />
                </span>
              </label>

              <label className="space-y-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Source</span>
                <span className="a26-select-wrap block">
                  <select
                    value={sourceFilter}
                    onChange={(event) => setSourceFilter(event.target.value)}
                    className="a26-select"
                  >
                    {SOURCE_LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="a26-select-icon" />
                </span>
              </label>

              <label className="space-y-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-secondary">Target</span>
                <span className="relative block">
                  <select
                    value={targetFilter}
                    onChange={(event) => setTargetFilter(event.target.value)}
                    className="a26-select"
                  >
                    {TARGET_LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                  <ChevronDown className="a26-select-icon" />
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
            <TriangleAlert className="h-[0.875rem] w-[0.875rem]" />
            {error}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-2xl border border-border-subtle/80">
          <div className="overflow-x-auto">
            <div className="max-h-[460px] overflow-y-auto" aria-busy={loading || refreshing}>
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
                              {expanded ? <ChevronUp className="h-[0.875rem] w-[0.875rem]" /> : <ChevronDown className="h-[0.875rem] w-[0.875rem]" />}
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
                                  <ClipboardCopy className="h-[0.875rem] w-[0.875rem]" />
                                  Copy JSON Payload
                                </button>

                                <button
                                  type="button"
                                  onClick={() => handleDeleteLog(row)}
                                  className="inline-flex items-center gap-1.5 rounded-xl border border-status-danger-border/70 bg-status-danger-bg/70 px-3 py-1.5 text-xs font-semibold text-status-danger-text transition-colors hover:bg-status-danger-bg"
                                  title="Remove this log from local activity view"
                                >
                                  <Trash2 className="h-[0.875rem] w-[0.875rem]" />
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
                    <ChevronLeft className="h-[0.875rem] w-[0.875rem]" />
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
                    <ChevronRight className="h-[0.875rem] w-[0.875rem]" />
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
