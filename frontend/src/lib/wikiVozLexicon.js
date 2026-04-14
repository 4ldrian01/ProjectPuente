import { useCallback, useEffect, useMemo, useState } from 'react'

export const DEFAULT_WIKI_VOZ_LEXICON_PATH = '/data/wiki_voz_kb.json'

let cachedLexiconEntries = null
let pendingLexiconRequest = null

function toStringSafe(value) {
  return String(value || '').trim()
}

function normalizeForPhraseScan(value) {
  const normalized = String(value || '')
    .normalize('NFKC')
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}_]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return normalized
}

function toTriggerWordsArray(value) {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .map((entry) => toStringSafe(entry))
    .filter(Boolean)
}

function normalizeWikiVozEntry(entry, index) {
  if (!entry || typeof entry !== 'object') {
    return null
  }

  const triggerWords = toTriggerWordsArray(entry.trigger_words)
  const fallbackTrigger = triggerWords[0] || ''
  const term = toStringSafe(entry.term || entry.title || fallbackTrigger || `wiki-voz-${index + 1}`)
  const definition = toStringSafe(entry.definition || entry.description)

  return {
    ...entry,
    id: entry.id || `wiki-voz-${index + 1}`,
    term,
    definition,
    image_url: toStringSafe(entry.image_url || entry.imageUrl),
    trigger_words: triggerWords,
  }
}

function normalizeLexiconPayload(payload) {
  const entries = Array.isArray(payload?.wiki_voz_entries)
    ? payload.wiki_voz_entries
    : (Array.isArray(payload) ? payload : [])

  return entries
    .map((entry, index) => normalizeWikiVozEntry(entry, index))
    .filter(Boolean)
}

function buildEntryKey(entry) {
  return String(entry.id || `${entry.term}|${entry.language}|${entry.category}`)
    .toLocaleLowerCase()
    .trim()
}

function buildCandidates(entries) {
  const candidates = []

  for (const entry of entries) {
    const rawTriggers = [
      ...(entry.trigger_words || []),
      entry.term,
      entry.title,
    ]

    const uniqueTriggers = [...new Set(rawTriggers.map((trigger) => toStringSafe(trigger)).filter(Boolean))]

    for (const trigger of uniqueTriggers) {
      const normalizedTrigger = normalizeForPhraseScan(trigger)
      if (!normalizedTrigger) {
        continue
      }

      candidates.push({
        entry,
        trigger,
        normalizedTrigger,
        normalizedLength: normalizedTrigger.length,
      })
    }
  }

  candidates.sort((left, right) => right.normalizedLength - left.normalizedLength)
  return candidates
}

export async function loadWikiVozLexicon(path = DEFAULT_WIKI_VOZ_LEXICON_PATH) {
  if (cachedLexiconEntries) {
    return cachedLexiconEntries
  }

  if (!pendingLexiconRequest) {
    pendingLexiconRequest = fetch(path, { cache: 'force-cache' })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load Wiki Voz lexicon (${response.status}).`)
        }

        return response.json()
      })
      .then((payload) => {
        const normalizedEntries = normalizeLexiconPayload(payload)
        cachedLexiconEntries = normalizedEntries
        pendingLexiconRequest = null
        return normalizedEntries
      })
      .catch((error) => {
        pendingLexiconRequest = null
        throw error
      })
  }

  return pendingLexiconRequest
}

export function resetWikiVozLexiconCache() {
  cachedLexiconEntries = null
  pendingLexiconRequest = null
}

export function findWikiVozMatches(text, entries) {
  const normalizedHaystack = normalizeForPhraseScan(text)
  if (!normalizedHaystack) {
    return []
  }

  const normalizedEntries = normalizeLexiconPayload(entries)
  if (normalizedEntries.length === 0) {
    return []
  }

  const haystack = ` ${normalizedHaystack} `
  const candidates = buildCandidates(normalizedEntries)
  const seen = new Set()
  const matches = []

  for (const candidate of candidates) {
    const phrase = ` ${candidate.normalizedTrigger} `
    if (!haystack.includes(phrase)) {
      continue
    }

    const key = buildEntryKey(candidate.entry)
    if (seen.has(key)) {
      continue
    }

    seen.add(key)
    matches.push({
      ...candidate.entry,
      matched_trigger: candidate.trigger,
      matchedTrigger: candidate.trigger,
      term: candidate.entry.term || candidate.trigger,
      definition: candidate.entry.definition,
      image_url: candidate.entry.image_url,
    })
  }

  return matches
}

export function useWikiVozLexicon(translatedText, options = {}) {
  const {
    enabled = true,
    path = DEFAULT_WIKI_VOZ_LEXICON_PATH,
    initialEntries = [],
  } = options

  const [entries, setEntries] = useState(() => normalizeLexiconPayload(initialEntries))
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')

    try {
      resetWikiVozLexiconCache()
      const nextEntries = await loadWikiVozLexicon(path)
      setEntries(nextEntries)
    } catch (refreshError) {
      setError(refreshError?.message || 'Failed to refresh Wiki Voz lexicon.')
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return undefined
    }

    let cancelled = false
    setLoading(true)
    setError('')

    loadWikiVozLexicon(path)
      .then((nextEntries) => {
        if (!cancelled) {
          setEntries(nextEntries)
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError?.message || 'Failed to load Wiki Voz lexicon.')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [enabled, path])

  const matches = useMemo(
    () => findWikiVozMatches(translatedText, entries),
    [entries, translatedText],
  )

  return {
    entries,
    matches,
    loading,
    error,
    refresh,
    path,
  }
}
