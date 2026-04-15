/**
 * translateWorkbench.js — Translation-screen constants and pure helper logic.
 * Summary: Houses language metadata, mock LID heuristics, input constraints, and workbench formatting helpers.
 */

export const SOURCE_VISIBLE = ['auto', 'en', 'tl']
export const SOURCE_DROPDOWN = ['cbk', 'ceb', 'hil', 'es']
export const TARGET_VISIBLE = ['cbk', 'ceb', 'hil', 'es']
export const TARGET_DROPDOWN = ['en', 'tl']

export const LANGUAGE_LABELS = {
  auto: 'Auto-Detect',
  en: 'English',
  tl: 'Tagalog',
  cbk: 'Chavacano',
  ceb: 'Cebuano/Bisaya',
  hil: 'Hiligaynon',
  es: 'Spanish',
}

export const SOCIOLINGUISTIC_SAMPLE_CASES = [
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

export const CHAR_LIMIT = 250
export const SOURCE_PLACEHOLDER = 'Enter Word to translate...'
export const TELEMETRY_POLL_INTERVAL_MS = 4500
export const FALLBACK_GPU_TOTAL_GB = 4
export const FALLBACK_RAM_TOTAL_GB = 8

export function clampPercent(value) {
  return Math.min(100, Math.max(0, Number(value) || 0))
}

export function formatGb(value) {
  return `${Number(value || 0).toFixed(2)} GB`
}

export function estimateTokenCount(text) {
  return Math.max(1, String(text || '').trim().split(/\s+/).filter(Boolean).length)
}

export function detectMockLanguage(text) {
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

export function escapeRegex(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function normalizeWikiCardEntry(entry) {
  if (!entry || typeof entry !== 'object') {
    return null
  }

  const term = String(entry.term || entry.title || entry.matched_trigger || '').trim()
  const definition = String(entry.definition || entry.description || '').trim()

  if (!term || !definition) {
    return null
  }

  return {
    ...entry,
    term,
    definition,
    image_url: entry.image_url || entry.imageUrl || '',
  }
}

export function buildWikiEntryKey(entry) {
  if (!entry) {
    return ''
  }

  return String(entry.id || `${entry.term}|${entry.language}|${entry.category}`)
    .toLowerCase()
    .trim()
}
