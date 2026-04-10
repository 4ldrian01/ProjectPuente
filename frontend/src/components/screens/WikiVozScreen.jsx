/**
 * WikiVozScreen.jsx — Enterprise Wiki-Voz exploration screen.
 *
 * Phase 4 upgrades:
 * - Expanded category taxonomy (Honorifics, Idioms, Historical, Mythology/Folklore)
 * - Language filter pinned to es / tl / cbk / hil / ceb
 * - Fuzzy-search command bar
 * - Masonry card grid with deterministic card aspect rhythm
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { Search, SlidersHorizontal, Sparkles, X } from 'lucide-react'
import { WIKI_VOZ_ENTRIES } from '../../data/wikiVozData'
import CulturalTermPopup from '../CulturalTermPopup'

const LOCAL_PLACEHOLDER_SRC = '/local-assets/placeholder.jpg'
const WIKI_PAGE_SIZE = 20
const MASONRY_ASPECTS = ['aspect-[4/3]', 'aspect-square', 'aspect-[5/6]', 'aspect-[16/10]', 'aspect-[3/4]']
const SEARCH_QUERY_MAX_LENGTH = 80
const FUZZY_MATCH_THRESHOLD = 42

const REQUIRED_LANGUAGE_KEYS = ['es', 'tl', 'cbk', 'hil', 'ceb']
const LANGUAGE_LABELS = {
  es: 'Spanish (es)',
  tl: 'Tagalog (tl)',
  cbk: 'Chavacano (cbk)',
  hil: 'Hiligaynon (hil)',
  ceb: 'Cebuano/Bisaya (ceb)',
}

const LANGUAGE_ALIASES = {
  es: ['es', 'spanish', 'espanol', 'español'],
  tl: ['tl', 'tagalog', 'filipino'],
  cbk: ['cbk', 'chavacano', 'chavacano zamboanga', 'zamboanga'],
  hil: ['hil', 'hiligaynon', 'ilonggo'],
  ceb: ['ceb', 'cebuano', 'bisaya', 'cebuano bisaya'],
}

const LANGUAGE_CATEGORY_REQUIREMENTS = {
  es: ['food', 'heritage', 'culture', 'expression', 'honorifics', 'idioms', 'historical', 'mythology-folklore', 'festival', 'family', 'craft', 'place', 'tradition', 'market', 'transport', 'music', 'spanish'],
  tl: ['food', 'heritage', 'culture', 'expression', 'lifestyle', 'honorifics', 'idioms', 'historical', 'mythology-folklore', 'festival', 'family', 'craft', 'place', 'tradition', 'market', 'transport', 'music'],
  cbk: ['food', 'heritage', 'culture', 'expression', 'lifestyle', 'festival', 'family', 'place', 'craft', 'music', 'honorifics', 'idioms', 'historical', 'mythology-folklore', 'spanish'],
  hil: ['food', 'heritage', 'culture', 'expression', 'festival', 'family', 'craft', 'place', 'tradition', 'market', 'honorifics', 'idioms', 'historical', 'mythology-folklore'],
  ceb: ['food', 'heritage', 'culture', 'expression', 'festival', 'family', 'craft', 'place', 'tradition', 'market', 'transport', 'music', 'honorifics', 'idioms', 'historical', 'mythology-folklore'],
}

const CATEGORY_LABELS = {
  food: 'Food',
  heritage: 'Heritage',
  culture: 'Culture',
  expression: 'Expression',
  lifestyle: 'Lifestyle',
  honorifics: 'Honorifics',
  idioms: 'Idioms',
  historical: 'Historical',
  'mythology-folklore': 'Mythology/Folklore',
  festival: 'Festival',
  family: 'Family',
  craft: 'Craft',
  place: 'Place',
  tradition: 'Tradition',
  market: 'Market',
  transport: 'Transport',
  music: 'Music',
  spanish: 'Spanish',
}

const CATEGORY_BASE_ORDER = [
  'food',
  'heritage',
  'culture',
  'expression',
  'lifestyle',
  'honorifics',
  'idioms',
  'historical',
  'mythology-folklore',
  'festival',
  'family',
  'craft',
  'place',
  'tradition',
  'market',
  'transport',
  'music',
  'spanish',
]

const CATEGORY_ALIASES = {
  honorifics: ['honorific', 'honorifics', 'titles', 'respect-title'],
  idioms: ['idiom', 'idioms', 'figure-of-speech'],
  historical: ['historical', 'history', 'historic'],
  'mythology-folklore': ['mythology-folklore', 'mythology', 'folklore', 'myths'],
  lifestyle: ['lifestyle'],
  expression: ['expression', 'expressions'],
  heritage: ['heritage'],
  culture: ['culture', 'cultural'],
  spanish: ['spanish', 'es'],
}

const REQUIRED_CATEGORIES = ['honorifics', 'idioms', 'historical', 'mythology-folklore']

const CATEGORY_ALIAS_TO_KEY = Object.entries(CATEGORY_ALIASES).reduce((acc, [key, aliases]) => {
  aliases.forEach((alias) => {
    acc[alias] = key
  })
  return acc
}, {})

const LANGUAGE_ALIAS_TO_KEY = Object.entries(LANGUAGE_ALIASES).reduce((acc, [key, aliases]) => {
  aliases.forEach((alias) => {
    acc[alias] = key
  })
  return acc
}, {})

function normalizeText(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function toCategoryLabel(categoryKey) {
  if (CATEGORY_LABELS[categoryKey]) {
    return CATEGORY_LABELS[categoryKey]
  }

  return String(categoryKey || '')
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(' ')
}

function normalizeCategoryKey(value) {
  const normalized = normalizeText(value)
    .replace(/[/_]+/g, '-')
    .replace(/\s+/g, '-')

  if (!normalized) return 'heritage'

  if (CATEGORY_ALIAS_TO_KEY[normalized]) {
    return CATEGORY_ALIAS_TO_KEY[normalized]
  }

  if (CATEGORY_BASE_ORDER.includes(normalized)) {
    return normalized
  }

  const matchedAlias = Object.keys(CATEGORY_ALIAS_TO_KEY).find((alias) => normalized.includes(alias))
  if (matchedAlias) {
    return CATEGORY_ALIAS_TO_KEY[matchedAlias]
  }

  return normalized
}

function normalizeLanguageCode(value) {
  const normalized = normalizeText(value)
    .replace(/[()]/g, ' ')
    .replace(/[/_-]+/g, ' ')
    .replace(/\s+/g, ' ')

  if (!normalized) {
    return 'cbk'
  }

  if (LANGUAGE_ALIAS_TO_KEY[normalized]) {
    return LANGUAGE_ALIAS_TO_KEY[normalized]
  }

  const matchedAlias = Object.keys(LANGUAGE_ALIAS_TO_KEY).find((alias) => normalized.includes(alias))
  if (matchedAlias) {
    return LANGUAGE_ALIAS_TO_KEY[matchedAlias]
  }

  return normalized
}

function sanitizeSearchQuery(value) {
  return String(value || '')
    .replace(/[<>{}`$]/g, '')
    .slice(0, SEARCH_QUERY_MAX_LENGTH)
}

function resolveLocalImageSrc(imageUrl) {
  if (!imageUrl) return LOCAL_PLACEHOLDER_SRC
  if (/^https?:\/\//i.test(imageUrl)) return LOCAL_PLACEHOLDER_SRC
  if (!imageUrl.startsWith('/')) return LOCAL_PLACEHOLDER_SRC
  return imageUrl
}

function hashValue(value) {
  const text = String(value ?? '')
  let hash = 0
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0
  }
  return hash
}

function getMasonryAspectClass(entry, index) {
  const signature = hashValue(entry?.id || `${entry?.term || ''}-${index}`)
  return MASONRY_ASPECTS[signature % MASONRY_ASPECTS.length]
}

function fuzzyScore(candidate, query) {
  if (!query) return 100

  if (!candidate) return 0

  if (candidate === query) {
    return 130
  }

  const exactIndex = candidate.indexOf(query)
  if (exactIndex >= 0) {
    return 110 - Math.min(40, exactIndex)
  }

  const candidateTokens = candidate.split(' ').filter(Boolean)
  const queryTokens = query.split(' ').filter(Boolean)

  if (queryTokens.length > 0) {
    const tokenHits = queryTokens.reduce((count, token) => (
      count + (candidateTokens.some((entryToken) => entryToken.startsWith(token) || entryToken.includes(token)) ? 1 : 0)
    ), 0)

    if (tokenHits === queryTokens.length) {
      return 82 + tokenHits
    }

    if (tokenHits > 0) {
      return 56 + tokenHits * 5
    }
  }

  let queryIndex = 0
  for (const char of candidate) {
    if (char === query[queryIndex]) {
      queryIndex += 1
      if (queryIndex === query.length) break
    }
  }

  const subsequenceRatio = queryIndex / query.length
  if (subsequenceRatio >= 0.72) {
    return Math.round(subsequenceRatio * 55)
  }

  return 0
}

function scoreEntry(entry, normalizedQuery) {
  if (!normalizedQuery) {
    return 100
  }

  const fields = [
    entry.normalizedTerm,
    entry.normalizedDefinition,
    entry.normalizedLanguage,
    entry.normalizedCategory,
  ]

  return fields.reduce((highest, field) => Math.max(highest, fuzzyScore(field, normalizedQuery)), 0)
}

export default function WikiVozScreen({ apiUrl, backendUp, ttsAvailable, notify }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [apiEntries, setApiEntries] = useState(null)
  const [apiError, setApiError] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedLanguage, setSelectedLanguage] = useState('all')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [visibleCount, setVisibleCount] = useState(WIKI_PAGE_SIZE)
  const [searchValidationMessage, setSearchValidationMessage] = useState('')

  const emitToast = useCallback((payload) => {
    if (typeof notify === 'function') {
      notify(payload)
    }
  }, [notify])

  useEffect(() => {
    let cancelled = false

    axios.get(`${apiUrl}/wiki/`, { timeout: 8000 })
      .then(({ data }) => {
        if (cancelled) return

        const mapped = (data.results || []).map((entry, index) => ({
          id: entry.id || `api-${index}`,
          term: entry.term,
          definition: entry.definition,
          imageUrl: entry.image_url || '',
          imageAlt: entry.term,
          sourceUrl: '',
          language: entry.language || 'Chavacano',
          category: entry.category || 'heritage',
        }))

        setApiEntries(mapped.length > 0 ? mapped : null)
        setVisibleCount(WIKI_PAGE_SIZE)
      })
      .catch(() => {
        if (!cancelled) {
          setApiError(true)
          emitToast({
            title: 'Wiki-Voz fallback enabled',
            message: 'Using offline Wiki-Voz entries because API data is unavailable.',
            variant: 'warning',
            durationMs: 4200,
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [apiUrl, emitToast])

  const allEntries = apiEntries || WIKI_VOZ_ENTRIES

  const normalizedQuery = useMemo(
    () => normalizeText(searchQuery),
    [searchQuery],
  )

  const normalizedEntries = useMemo(() => (
    allEntries.map((entry) => {
      const categoryKey = normalizeCategoryKey(entry.category)
      const languageCode = normalizeLanguageCode(entry.language)

      return {
        ...entry,
        categoryKey,
        languageCode,
        normalizedTerm: normalizeText(entry.term),
        normalizedDefinition: normalizeText(entry.definition),
        normalizedLanguage: normalizeText(entry.language),
        normalizedCategory: normalizeText(categoryKey),
      }
    })
  ), [allEntries])

  const scopedEntriesForCategories = useMemo(() => (
    selectedLanguage === 'all'
      ? normalizedEntries
      : normalizedEntries.filter((entry) => entry.languageCode === selectedLanguage)
  ), [normalizedEntries, selectedLanguage])

  const categoryCounts = useMemo(() => (
    scopedEntriesForCategories.reduce((acc, entry) => {
      if (!entry.categoryKey) return acc
      acc[entry.categoryKey] = (acc[entry.categoryKey] || 0) + 1
      return acc
    }, {})
  ), [scopedEntriesForCategories])

  const categoryOptions = useMemo(() => {
    const discovered = new Set(
      scopedEntriesForCategories
        .map((entry) => entry.categoryKey)
        .filter(Boolean),
    )

    REQUIRED_CATEGORIES.forEach((categoryKey) => discovered.add(categoryKey))

    const languageScopedRequirements = selectedLanguage === 'all'
      ? Object.values(LANGUAGE_CATEGORY_REQUIREMENTS).flat()
      : (LANGUAGE_CATEGORY_REQUIREMENTS[selectedLanguage] || [])

    languageScopedRequirements.forEach((categoryKey) => discovered.add(categoryKey))

    const ordered = CATEGORY_BASE_ORDER.filter((categoryKey) => discovered.has(categoryKey))
    const extras = [...discovered]
      .filter((categoryKey) => !CATEGORY_BASE_ORDER.includes(categoryKey))
      .sort((a, b) => a.localeCompare(b))

    return ['all', ...ordered, ...extras]
  }, [scopedEntriesForCategories, selectedLanguage])

  const languageOptions = useMemo(() => {
    const discovered = new Set(
      normalizedEntries
        .map((entry) => entry.languageCode)
        .filter(Boolean),
    )

    REQUIRED_LANGUAGE_KEYS.forEach((languageKey) => discovered.add(languageKey))

    const required = REQUIRED_LANGUAGE_KEYS
      .filter((languageKey) => discovered.has(languageKey))
      .map((languageKey) => ({ key: languageKey, label: LANGUAGE_LABELS[languageKey] || languageKey.toUpperCase() }))

    const extras = [...discovered]
      .filter((languageKey) => !REQUIRED_LANGUAGE_KEYS.includes(languageKey))
      .sort((a, b) => a.localeCompare(b))
      .map((languageKey) => ({
        key: languageKey,
        label: LANGUAGE_LABELS[languageKey] || languageKey.toUpperCase(),
      }))

    return [{ key: 'all', label: 'All Languages' }, ...required, ...extras]
  }, [normalizedEntries])

  const activeCategory = categoryOptions.includes(selectedCategory) ? selectedCategory : 'all'

  const filteredEntries = useMemo(() => {
    const entriesWithScore = normalizedEntries
      .map((entry) => {
        const searchScore = scoreEntry(entry, normalizedQuery)

        return {
          ...entry,
          searchScore,
        }
      })
      .filter((entry) => {
        const matchesCategory = activeCategory === 'all' || entry.categoryKey === activeCategory
        const matchesLanguage = selectedLanguage === 'all' || entry.languageCode === selectedLanguage
        const matchesSearch = !normalizedQuery || entry.searchScore >= FUZZY_MATCH_THRESHOLD

        return matchesCategory && matchesLanguage && matchesSearch
      })

    if (normalizedQuery) {
      entriesWithScore.sort((a, b) => {
        if (b.searchScore !== a.searchScore) {
          return b.searchScore - a.searchScore
        }
        return a.term.localeCompare(b.term)
      })
    }

    return entriesWithScore
  }, [activeCategory, normalizedEntries, normalizedQuery, selectedLanguage])

  const hasActiveFilters = activeCategory !== 'all' || selectedLanguage !== 'all'
  const visibleEntries = filteredEntries.slice(0, visibleCount)
  const hasMoreEntries = visibleCount < filteredEntries.length
  const filteredLanguageCount = useMemo(() => {
    const uniqueLanguages = new Set(
      filteredEntries
        .map((entry) => entry.languageCode)
        .filter(Boolean),
    )

    return uniqueLanguages.size
  }, [filteredEntries])
  const dataSourceLabel = apiEntries ? 'Live API dataset' : 'Offline fallback dataset'

  const handleViewMore = () => {
    setVisibleCount((previous) => Math.min(previous + WIKI_PAGE_SIZE, filteredEntries.length))
  }

  const handleSearchChange = (event) => {
    const rawValue = event.target.value
    const sanitizedValue = sanitizeSearchQuery(rawValue)

    setSearchQuery(sanitizedValue)
    setVisibleCount(WIKI_PAGE_SIZE)

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

  const handleCategoryChange = (categoryKey) => {
    setSelectedCategory(categoryKey)
    setVisibleCount(WIKI_PAGE_SIZE)
  }

  const handleLanguageChange = (languageKey) => {
    setSelectedLanguage(languageKey)
    setVisibleCount(WIKI_PAGE_SIZE)
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-1 flex-col space-y-5 pb-2">
      <div className="a26-surface relative overflow-hidden p-4 sm:p-5 lg:p-6">
        <div aria-hidden className="pointer-events-none absolute -right-12 -top-16 h-44 w-44 rounded-full bg-accent-magenta/15 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -left-10 bottom-[-5.5rem] h-40 w-40 rounded-full bg-accent-gold/15 blur-3xl" />

        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="a26-subtitle">Wiki-Voz Intelligence Panel</p>
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Cultural Term Explorer</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary sm:text-[15px]">
              Scan heritage terms across Philippine languages with fuzzy search, language-scoped filters, and quick card drill-down.
            </p>
          </div>

          <div className="flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-wide">
            <span className="a26-chip">
              {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'}
            </span>
            <span className="a26-chip">{filteredLanguageCount} language{filteredLanguageCount === 1 ? '' : 's'}</span>
            <span className="a26-chip">{dataSourceLabel}</span>
          </div>
        </div>
      </div>

      {/* Fuzzy Search Header */}
      <div className="a26-surface p-4 sm:p-5">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            maxLength={SEARCH_QUERY_MAX_LENGTH}
            placeholder="Fuzzy search: term, phrase, definition, category..."
            className="w-full rounded-xl border border-border-subtle bg-bg-elevated/75 py-3 pl-9 pr-24 text-sm text-text-primary placeholder-text-secondary/60 shadow-inner transition-all duration-300 focus:border-accent-magenta/70 focus:outline-none focus:ring-2 focus:ring-accent-magenta/20"
          />

          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('')
                setSearchValidationMessage('')
              }}
              className="a26-button-ghost absolute right-11 top-1/2 -translate-y-1/2 p-1"
              aria-label="Clear search"
              title="Clear search"
            >
              <X className="h-4 w-4" />
            </button>
          )}

          <button
            onClick={() => setFiltersOpen((previous) => !previous)}
            className={`absolute right-2 top-1/2 -translate-y-1/2 rounded-xl border border-transparent p-1.5 transition-all duration-300 active:scale-[0.98] ${
              filtersOpen || hasActiveFilters
                ? 'border-accent-magenta/35 bg-accent-magenta/15 text-accent-magenta'
                : 'text-text-secondary hover:border-border-subtle hover:bg-bg-elevated hover:text-text-primary'
            }`}
            title="Toggle filters"
            aria-label="Toggle filters"
            aria-expanded={filtersOpen}
          >
            <SlidersHorizontal className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px]">
          <span className={searchValidationMessage ? 'text-status-warning-text' : 'text-text-secondary'}>
            {searchValidationMessage || 'Fuzzy scoring active (term, definition, language, category).'}
          </span>
          <span className="text-text-secondary">{searchQuery.length}/{SEARCH_QUERY_MAX_LENGTH}</span>
        </div>

        {filtersOpen && (
          <div className="mt-4 grid gap-4 rounded-2xl border border-border-subtle/80 bg-bg-elevated/35 p-3.5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Categories</p>
              <div className="max-h-40 overflow-y-auto pr-1">
                <div className="flex flex-wrap gap-2">
                {categoryOptions.map((categoryKey) => (
                  <button
                    key={categoryKey}
                    onClick={() => handleCategoryChange(categoryKey)}
                    className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition-all duration-200 active:scale-[0.98] ${
                      activeCategory === categoryKey
                        ? 'bg-accent-gold text-bg-dark'
                        : 'border border-border-subtle bg-bg-card text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                    }`}
                  >
                    {categoryKey === 'all'
                      ? 'All'
                      : `${toCategoryLabel(categoryKey)} (${categoryCounts[categoryKey] || 0})`}
                  </button>
                ))}
                </div>
              </div>
              <p className="mt-1.5 text-[10px] text-text-secondary/90">
                {selectedLanguage === 'all'
                  ? 'Category options combine all language taxonomies.'
                  : `Categories are scoped for ${LANGUAGE_LABELS[selectedLanguage] || selectedLanguage.toUpperCase()}.`}
              </p>
            </div>

            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Languages</p>
              <div className="flex flex-wrap gap-2">
                {languageOptions.map((language) => (
                  <button
                    key={language.key}
                    onClick={() => handleLanguageChange(language.key)}
                    className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition-all duration-200 active:scale-[0.98] ${
                      selectedLanguage === language.key
                        ? 'bg-accent-magenta text-white'
                        : 'border border-border-subtle bg-bg-card text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                    }`}
                  >
                    {language.label}
                  </button>
                ))}
              </div>
            </div>

            {hasActiveFilters && (
              <div className="flex items-center justify-between rounded-xl border border-border-subtle/75 bg-bg-card/65 px-3 py-2 lg:col-span-2">
                <span className="text-[11px] font-medium text-text-secondary">Filters are active on this result set.</span>
                <button
                  onClick={() => {
                    handleCategoryChange('all')
                    handleLanguageChange('all')
                  }}
                  className="rounded-xl border border-accent-magenta/45 px-3 py-1 text-xs font-semibold text-accent-magenta transition-colors hover:bg-accent-magenta/10"
                >
                  Clear filters
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {apiError && (
        <div className="rounded-xl border border-status-warning-border/60 bg-status-warning-bg/70 px-3 py-2 text-xs text-status-warning-text">
          Backend Wiki endpoint unavailable, showing offline fallback entries.
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border-subtle/75 bg-bg-card/55 px-3 py-2 text-sm text-text-secondary">
        <span>
          {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'} found
          {hasActiveFilters ? ' • filters active' : ''}
        </span>

        <span className="inline-flex items-center gap-1 rounded-full border border-border-subtle px-2 py-0.5 text-[11px]">
          <Sparkles className="h-3.5 w-3.5 text-accent-magenta" />
          Fuzzy
        </span>
      </div>

      {/* Masonry Grid */}
      <div className="columns-1 gap-5 [column-fill:balance] sm:columns-2 xl:columns-3 2xl:columns-4">
        {visibleEntries.map((entry, index) => (
          <article
            key={entry.id}
            className="a26-surface group mb-5 break-inside-avoid overflow-hidden"
          >
            <div
              className={`relative w-full cursor-pointer overflow-hidden bg-bg-elevated ${getMasonryAspectClass(entry, index)}`}
              onClick={() => setSelectedEntry(entry)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  setSelectedEntry(entry)
                }
              }}
              role="button"
              tabIndex={0}
              aria-label={`Open details for ${entry.term}`}
            >
              <img
                src={resolveLocalImageSrc(entry.imageUrl)}
                alt={entry.imageAlt || entry.term}
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                loading="lazy"
                onError={(event) => {
                  event.currentTarget.src = LOCAL_PLACEHOLDER_SRC
                }}
              />

              <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-linear-to-t from-black/85 via-black/30 to-transparent px-3.5 pb-3 pt-8">
                <div className="flex items-end justify-between gap-2">
                  <h3 className="line-clamp-2 text-base font-bold text-white sm:text-lg">{entry.term}</h3>
                  <span className="shrink-0 rounded-full bg-accent-magenta/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white backdrop-blur-sm">
                    {(LANGUAGE_LABELS[entry.languageCode] || entry.languageCode).replace(/\s*\([^)]*\)\s*/g, '')}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-3 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-full border border-border-subtle bg-bg-elevated/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                  {toCategoryLabel(entry.categoryKey)}
                </span>
                {normalizedQuery && (
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                    Score {entry.searchScore}
                  </span>
                )}
              </div>

              <p className="line-clamp-3 text-sm leading-relaxed text-text-secondary">
                {entry.definition}
              </p>

              <button
                onClick={() => setSelectedEntry(entry)}
                className="a26-button-primary w-full px-4 py-2 text-sm font-semibold"
              >
                Open Details
              </button>
            </div>
          </article>
        ))}
      </div>

      {filteredEntries.length > 0 && (
        <div className="mt-2 flex items-center justify-center">
          {hasMoreEntries ? (
            <button
              onClick={handleViewMore}
              className="a26-button-ghost px-4 py-2 text-sm font-semibold text-accent-magenta"
            >
              View More ({Math.min(WIKI_PAGE_SIZE, filteredEntries.length - visibleCount)} next)
            </button>
          ) : (
            <span className="text-xs text-text-secondary/80">You have reached the end of the current results.</span>
          )}
        </div>
      )}

      {filteredEntries.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center py-12">
          <span className="mb-3 text-4xl">🔍</span>
          <p className="text-center text-text-secondary">
            No entries matched your fuzzy query.
          </p>
          <button
            onClick={() => {
              setSearchQuery('')
              setSearchValidationMessage('')
            }}
            className="mt-3 text-sm font-medium text-accent-magenta hover:underline"
          >
            Clear search
          </button>
        </div>
      )}

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
