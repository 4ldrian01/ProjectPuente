/**
 * WikiVozScreen.jsx — Data-driven Wiki-Voz panel bound to local wiki_voz_kb.json.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { Search, X } from 'lucide-react'
import CulturalTermPopup from '../CulturalTermPopup'
import { withApiKeyHeaders } from '../../lib/apiAuth'

const LOCAL_PLACEHOLDER_SRC = '/local-assets/placeholder.jpg'
const SEARCH_QUERY_MAX_LENGTH = 80
const ALLOWED_CATEGORIES = ['Idioms', 'False Cognates', 'Honorifics', 'Expressions']
const CARD_BATCH_SIZE = 20

const CATEGORY_ALIAS_TO_CANONICAL = {
  idiom: 'Idioms',
  idioms: 'Idioms',
  'false cognate': 'False Cognates',
  'false cognates': 'False Cognates',
  honorific: 'Honorifics',
  honorifics: 'Honorifics',
  expression: 'Expressions',
  expressions: 'Expressions',
  culture: 'Expressions',
}

function normalizeText(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function sanitizeSearchQuery(value) {
  return String(value || '')
    .replace(/[<>{}`$]/g, '')
    .slice(0, SEARCH_QUERY_MAX_LENGTH)
}

function isEditableTarget(target) {
  return target instanceof HTMLElement && (
    target.tagName === 'INPUT'
    || target.tagName === 'TEXTAREA'
    || target.tagName === 'SELECT'
    || target.isContentEditable
  )
}

function resolveLocalImageSrc(imageUrl) {
  if (!imageUrl) return LOCAL_PLACEHOLDER_SRC
  if (/^https?:\/\//i.test(imageUrl)) return LOCAL_PLACEHOLDER_SRC
  if (!imageUrl.startsWith('/')) return LOCAL_PLACEHOLDER_SRC
  return imageUrl
}

function normalizeCategory(rawValue) {
  const normalized = String(rawValue || '').trim().toLowerCase()
  const canonical = CATEGORY_ALIAS_TO_CANONICAL[normalized]
  return canonical && ALLOWED_CATEGORIES.includes(canonical) ? canonical : null
}

function toCardEntry(entry, index) {
  const triggerWords = Array.isArray(entry?.trigger_words)
    ? [...new Set(entry.trigger_words.map((term) => String(term || '').trim()).filter(Boolean))]
    : []

  const title = String(entry?.title || entry?.term || triggerWords[0] || '').trim()
  const description = String(entry?.description || entry?.definition || '').trim()
  const language = String(entry?.language || 'Unknown').trim() || 'Unknown'
  const category = normalizeCategory(entry?.category)

  if (!category) {
    return null
  }

  return {
    id: entry?.id || `wiki-${index + 1}`,
    term: title,
    title,
    definition: description,
    description,
    language,
    category,
    trigger_words: triggerWords,
    imageUrl: String(entry?.image_url || entry?.imageUrl || '').trim(),
    image_url: String(entry?.image_url || entry?.imageUrl || '').trim(),
  }
}

export default function WikiVozScreen({ apiUrl, backendUp, ttsAvailable, notify }) {
  const rootRef = useRef(null)
  const appendTimerRef = useRef(null)

  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchValidationMessage, setSearchValidationMessage] = useState('')
  const [selectedLanguage, setSelectedLanguage] = useState('all')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [visibleCount, setVisibleCount] = useState(CARD_BATCH_SIZE)
  const [isAppending, setIsAppending] = useState(false)

  const emitToast = useCallback((payload) => {
    if (typeof notify === 'function') {
      notify(payload)
    }
  }, [notify])

  useEffect(() => {
    let cancelled = false

    const loadWikiVozFromApi = async () => {
      setLoading(true)
      setLoadError('')

      try {
        const { data } = await axios.get(`${apiUrl}/wiki/`, {
          timeout: 8000,
          headers: withApiKeyHeaders(),
        })

        const rawEntries = Array.isArray(data?.results)
          ? data.results
          : (Array.isArray(data?.wiki_voz_entries) ? data.wiki_voz_entries : [])
        const mapped = rawEntries
          .map((entry, index) => toCardEntry(entry, index))
          .filter((entry) => entry && entry.term && entry.definition)

        if (!cancelled) {
          setEntries(mapped)
        }
      } catch (error) {
        const payload = error?.response?.data
        const message = String(payload?.error || '').trim()
          || error?.message
          || 'Unable to load Wiki-Voz entries from API.'
        if (!cancelled) {
          setLoadError(message)
          setEntries([])
          emitToast({
            title: 'Wiki-Voz data unavailable',
            message,
            variant: 'error',
            durationMs: 4800,
          })
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    loadWikiVozFromApi()
    return () => {
      cancelled = true
    }
  }, [apiUrl, emitToast])

  const normalizedQuery = useMemo(() => normalizeText(searchQuery), [searchQuery])

  const languageOptions = useMemo(() => {
    const dynamic = [...new Set(entries.map((entry) => entry.language).filter(Boolean))]
      .sort((left, right) => left.localeCompare(right))

    return [{ key: 'all', label: 'All Languages' }, ...dynamic.map((language) => ({ key: language, label: language }))]
  }, [entries])

  const categoryOptions = useMemo(() => {
    const languageScopedEntries = selectedLanguage === 'all'
      ? entries
      : entries.filter((entry) => entry.language === selectedLanguage)

    const dynamic = ALLOWED_CATEGORIES.filter((category) => (
      languageScopedEntries.some((entry) => entry.category === category)
    ))

    return [{ key: 'all', label: 'All Categories' }, ...dynamic.map((category) => ({ key: category, label: category }))]
  }, [entries, selectedLanguage])

  const filteredEntries = useMemo(() => {
    const result = entries.filter((entry) => {
      const languageMatch = selectedLanguage === 'all' || entry.language === selectedLanguage
      const categoryMatch = selectedCategory === 'all' || entry.category === selectedCategory

      if (!languageMatch || !categoryMatch) {
        return false
      }

      if (!normalizedQuery) {
        return true
      }

      const searchable = [
        entry.term,
        entry.definition,
        entry.category,
        entry.language,
        ...(entry.trigger_words || []),
      ]
        .map((value) => normalizeText(value))
        .join(' ')

      return searchable.includes(normalizedQuery)
    })

    return result.sort((left, right) => left.term.localeCompare(right.term))
  }, [entries, normalizedQuery, selectedCategory, selectedLanguage])

  useEffect(() => {
    setVisibleCount(CARD_BATCH_SIZE)
  }, [normalizedQuery, selectedLanguage, selectedCategory])

  useEffect(() => {
    setVisibleCount((previous) => {
      if (filteredEntries.length === 0) {
        return CARD_BATCH_SIZE
      }

      return Math.max(CARD_BATCH_SIZE, Math.min(previous, filteredEntries.length))
    })
  }, [filteredEntries.length])

  const visibleEntries = useMemo(
    () => filteredEntries.slice(0, visibleCount),
    [filteredEntries, visibleCount],
  )

  const visibleRangeStart = filteredEntries.length === 0 ? 0 : 1
  const visibleRangeEnd = visibleEntries.length
  const hasMoreEntries = visibleEntries.length < filteredEntries.length

  const totalCountLabel = filteredEntries.length === entries.length
    ? `${entries.length} total`
    : `${filteredEntries.length} filtered of ${entries.length}`

  const handleLanguageChange = (language) => {
    setSelectedLanguage(language)
    setSelectedCategory('all')
  }

  const handleCategoryChange = (category) => {
    setSelectedCategory(category)
  }

  const handleSearchChange = (event) => {
    const rawValue = event.target.value
    const sanitizedValue = sanitizeSearchQuery(rawValue)

    setSearchQuery(sanitizedValue)

    if (rawValue.length > SEARCH_QUERY_MAX_LENGTH) {
      setSearchValidationMessage(`Search is limited to ${SEARCH_QUERY_MAX_LENGTH} characters.`)
      return
    }

    if (rawValue !== sanitizedValue) {
      setSearchValidationMessage('Unsafe symbols were removed from the search input.')
      return
    }

    setSearchValidationMessage('')
  }

  const clearAppendTimer = useCallback(() => {
    if (appendTimerRef.current) {
      window.clearTimeout(appendTimerRef.current)
      appendTimerRef.current = null
    }
  }, [])

  const runAppendTransition = useCallback((computeNextVisibleCount) => {
    clearAppendTimer()
    setIsAppending(true)
    setVisibleCount((previous) => computeNextVisibleCount(previous))
    appendTimerRef.current = window.setTimeout(() => {
      setIsAppending(false)
      appendTimerRef.current = null
    }, 260)
  }, [clearAppendTimer])

  const handleViewMore = useCallback(() => {
    if (!hasMoreEntries) {
      return
    }

    runAppendTransition((previous) => Math.min(filteredEntries.length, previous + CARD_BATCH_SIZE))
  }, [filteredEntries.length, hasMoreEntries, runAppendTransition])

  const handleViewAll = useCallback(() => {
    if (!hasMoreEntries) {
      return
    }

    runAppendTransition(() => filteredEntries.length)
  }, [filteredEntries.length, hasMoreEntries, runAppendTransition])

  const handleResetToFirstBatch = useCallback(() => {
    clearAppendTimer()
    setIsAppending(false)
    setVisibleCount(CARD_BATCH_SIZE)
  }, [clearAppendTimer])

  useEffect(() => {
    return () => {
      clearAppendTimer()
    }
  }, [clearAppendTimer])

  useEffect(() => {
    const handlePaginationShortcuts = (event) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) {
        return
      }

      if (isEditableTarget(event.target)) {
        return
      }

      if (selectedEntry) {
        return
      }

      const rootElement = rootRef.current
      if (!rootElement || rootElement.offsetParent === null) {
        return
      }

      if ((event.key === ']' || event.key === 'ArrowRight') && hasMoreEntries) {
        event.preventDefault()
        handleViewMore()
        return
      }

      if (event.key === 'End' && hasMoreEntries) {
        event.preventDefault()
        handleViewAll()
        return
      }

      if (event.key === 'Home' && visibleEntries.length > CARD_BATCH_SIZE) {
        event.preventDefault()
        handleResetToFirstBatch()
      }
    }

    window.addEventListener('keydown', handlePaginationShortcuts)
    return () => {
      window.removeEventListener('keydown', handlePaginationShortcuts)
    }
  }, [handleResetToFirstBatch, handleViewAll, handleViewMore, hasMoreEntries, selectedEntry, visibleEntries.length])

  return (
    <div ref={rootRef} className="mx-auto flex w-full max-w-7xl flex-1 flex-col space-y-5 pb-2">
      <div className="a26-surface relative overflow-hidden p-4 sm:p-5 lg:p-6">
        <div aria-hidden className="pointer-events-none absolute -right-12 -top-16 h-44 w-44 rounded-full bg-accent-magenta/15 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -left-10 bottom-[-5.5rem] h-40 w-40 rounded-full bg-accent-gold/15 blur-3xl" />

        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="a26-subtitle">Wiki-Voz Intelligence Panel</p>
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Cultural Term Explorer</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary sm:text-[15px]">
              Data-driven sociolinguistic cards synchronized with wiki_voz_kb.json for explainable translation context.
            </p>
          </div>

          <div className="flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-wide">
            <span className="a26-chip">{totalCountLabel}</span>
            <span className="a26-chip">{languageOptions.length - 1} languages</span>
            <span className="a26-chip">{categoryOptions.length - 1} categories</span>
          </div>
        </div>
      </div>

      <div className="a26-surface p-4 sm:p-5">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            maxLength={SEARCH_QUERY_MAX_LENGTH}
            placeholder="Search title, description, category, language, trigger words..."
            className="w-full rounded-xl border border-border-subtle bg-bg-elevated/75 py-3 pl-9 pr-10 text-sm text-text-primary placeholder-text-secondary/60 shadow-inner transition-all duration-300 focus:border-accent-magenta/70 focus:outline-none focus:ring-2 focus:ring-accent-magenta/20"
          />

          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('')
                setSearchValidationMessage('')
              }}
              className="a26-button-ghost absolute right-2 top-1/2 -translate-y-1/2 p-1"
              aria-label="Clear search"
              title="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px]">
          <span className={searchValidationMessage ? 'text-status-warning-text' : 'text-text-secondary'}>
            {searchValidationMessage || 'Live API filtering is active.'}
          </span>
          <span className="text-text-secondary">{searchQuery.length}/{SEARCH_QUERY_MAX_LENGTH}</span>
        </div>

        <div className="mt-4 space-y-3 rounded-2xl border border-border-subtle/80 bg-bg-elevated/35 p-3.5">
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Language</p>
            <div className="flex flex-wrap gap-2">
              {languageOptions.map((option) => (
                <button
                  type="button"
                  key={option.key}
                  onClick={() => handleLanguageChange(option.key)}
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition-all duration-200 active:scale-[0.98] ${
                    selectedLanguage === option.key
                      ? 'bg-accent-magenta text-white'
                      : 'border border-border-subtle bg-bg-card text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Category</p>
            <div className="flex flex-wrap gap-2">
              {categoryOptions.map((option) => (
                <button
                  type="button"
                  key={option.key}
                  onClick={() => handleCategoryChange(option.key)}
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition-all duration-200 active:scale-[0.98] ${
                    selectedCategory === option.key
                      ? 'bg-accent-gold text-bg-dark'
                      : 'border border-border-subtle bg-bg-card text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {loadError ? (
        <div className="rounded-xl border border-status-warning-border/60 bg-status-warning-bg/70 px-3 py-2 text-xs text-status-warning-text">
          {loadError}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border-subtle/75 bg-bg-card/55 px-3 py-2 text-sm text-text-secondary">
        <span>
          {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'} found
        </span>
        <span className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-2 py-0.5 text-[11px]">
            {totalCountLabel}
        </span>
      </div>

      <div className={`rounded-2xl border border-border-subtle/70 bg-bg-card/20 p-3 ${isAppending ? 'a26-list-appending' : ''}`} aria-busy={loading || isAppending}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visibleEntries.map((entry) => (
            <article
              key={entry.id}
              className="a26-surface overflow-hidden"
            >
              <div className="relative h-36 w-full overflow-hidden bg-bg-elevated">
                <img
                  src={resolveLocalImageSrc(entry.imageUrl)}
                  alt={entry.term}
                  className="h-full w-full object-cover"
                  loading="lazy"
                  onError={(event) => {
                    event.currentTarget.src = LOCAL_PLACEHOLDER_SRC
                  }}
                />
              </div>

              <div className="space-y-3 p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="rounded-full border border-border-subtle bg-bg-elevated/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                    {entry.category}
                  </span>
                  <span className="rounded-full bg-accent-magenta/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-accent-magenta">
                    {entry.language}
                  </span>
                </div>

                <h3 className="line-clamp-2 text-base font-bold text-text-primary">{entry.term}</h3>

                <p className="line-clamp-4 text-sm leading-relaxed text-text-secondary">
                  {entry.definition}
                </p>

                {(entry.trigger_words || []).length > 0 ? (
                  <div className="rounded-xl border border-border-subtle/70 bg-bg-elevated/40 px-2.5 py-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-text-secondary">Trigger Words</p>
                    <p className="mt-1 line-clamp-2 text-xs text-text-secondary">
                      {(entry.trigger_words || []).join(', ')}
                    </p>
                  </div>
                ) : null}

                <button
                  type="button"
                  onClick={() => setSelectedEntry(entry)}
                  className="w-full rounded-xl bg-accent-magenta px-3 py-2 text-xs font-semibold uppercase tracking-wide text-white transition-all duration-200 hover:brightness-110 active:scale-[0.99]"
                >
                  View Details
                </button>
              </div>
            </article>
          ))}
        </div>

        {!loading && filteredEntries.length === 0 ? (
          <div className="py-12 text-center text-text-secondary">
            No entries matched the current filters.
          </div>
        ) : null}
      </div>

      {filteredEntries.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-xl border border-border-subtle/75 bg-bg-card/45 px-3 py-2.5 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <span className="text-xs sm:text-sm" aria-live="polite">
            Showing {visibleRangeStart}-{visibleRangeEnd} of {filteredEntries.length} entries
          </span>

          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="a26-pagination-hint">
              Shortcuts: ] / Right Arrow = +20, End = all, Home = first 20
            </span>

            {hasMoreEntries ? (
              <button
                type="button"
                onClick={handleViewMore}
                disabled={isAppending}
                className="a26-button-primary px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-60"
                aria-keyshortcuts="] ArrowRight"
                title="Shortcut: ] or Right Arrow"
              >
                {isAppending ? 'Loading...' : 'View 20 More'}
              </button>
            ) : null}

            {hasMoreEntries ? (
              <button
                type="button"
                onClick={handleViewAll}
                disabled={isAppending}
                className="a26-button-ghost px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-60"
                aria-keyshortcuts="End"
                title="Shortcut: End"
              >
                View All
              </button>
            ) : null}

            {visibleEntries.length > CARD_BATCH_SIZE ? (
              <button
                type="button"
                onClick={handleResetToFirstBatch}
                disabled={isAppending}
                className="a26-button-ghost px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide"
                aria-keyshortcuts="Home"
                title="Shortcut: Home"
              >
                Back To First 20
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {selectedEntry && (
        <CulturalTermPopup
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
          apiUrl={apiUrl}
          backendUp={backendUp}
          ttsAvailable={ttsAvailable}
        />
      )}
    </div>
  )
}
