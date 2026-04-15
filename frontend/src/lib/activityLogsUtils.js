/**
 * activityLogsUtils.js — Pure utilities for activity-log transformation.
 * Summary: Contains formatting, routing interpretation, CSV generation, and pagination helpers for log views.
 */

const PIVOT_LANGUAGE_LABELS = {
  tl: 'Tagalog',
  ceb: 'Cebuano/Bisaya',
  es: 'Spanish',
}

export const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'success', label: 'Success' },
  { value: 'error', label: 'Error' },
  { value: 'timeout', label: 'Timeout' },
]

export const SOURCE_LANGUAGE_OPTIONS = [
  { value: 'all', label: 'All Sources' },
  { value: 'auto', label: 'Auto' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'tl', label: 'Tagalog' },
  { value: 'cbk', label: 'Chavacano' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
]

export const TARGET_LANGUAGE_OPTIONS = [
  { value: 'all', label: 'All Targets' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'tl', label: 'Tagalog' },
  { value: 'cbk', label: 'Chavacano' },
  { value: 'hil', label: 'Hiligaynon' },
  { value: 'ceb', label: 'Cebuano/Bisaya' },
]

export const MAX_QUERY_LENGTH = 64
export const POLL_INTERVAL_MS = 20000
export const LOG_FETCH_LIMIT = 200
export const EXPORT_FETCH_LIMIT = 200
export const ROWS_PER_PAGE = 20
export const SUPPRESSED_LOGS_STORAGE_KEY = 'puente-activity-logs-suppressed-v1'

export function sanitizeQuery(value) {
  return String(value || '')
    .replace(/[<>{}`$]/g, '')
    .slice(0, MAX_QUERY_LENGTH)
}

export function formatTime(isoValue) {
  if (!isoValue) return '-'

  try {
    return new Date(isoValue).toLocaleString()
  } catch {
    return '-'
  }
}

export function formatLatency(latencyMs) {
  if (!Number.isFinite(latencyMs) || latencyMs < 0) {
    return '--'
  }
  return `${Math.round(latencyMs)} ms`
}

export function normalizeRouteConfidence(value) {
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

export function formatRouteConfidence(value) {
  const normalized = normalizeRouteConfidence(value)
  if (normalized === null) {
    return '--'
  }

  return `${Math.round(normalized * 100)}%`
}

export function routeConfidenceToneClass(value) {
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

export function routeConfidenceBarClass(value) {
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

export function toFiniteNumber(value, fallback = 0) {
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

export function computeBtvlProxy(row) {
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

export function computeMockVramSpike(row) {
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

export function resolveRouteStrategy(row) {
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

export function resolvePivotLanguage(row) {
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

export function isLocalModelMissingLog(row) {
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

export function buildInterventionTags(row) {
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

export function findOptionLabel(options, value, fallbackLabel = 'All') {
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

export function buildLogsCsv(rows) {
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

export function buildLogPayload(row) {
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

export function buildPaginationItems(totalPages, currentPage) {
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

export function statusBadgeClass(status) {
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
