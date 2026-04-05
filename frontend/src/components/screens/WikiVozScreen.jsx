/**
 * WikiVozScreen.jsx — Cultural encyclopedia screen
 * Fetches cultural terms from /api/wiki/ (PostgreSQL-backed).
 * Falls back to hardcoded wikiVozData.js seed data if API unreachable.
 * Features: Search bar, category chips, responsive masonry-style desktop grid.
 */

import { useState, useMemo, useEffect } from 'react'
import axios from 'axios'
import { FunnelIcon, SearchIcon } from '../icons/NavIcons'
import { WIKI_VOZ_ENTRIES } from '../../data/wikiVozData'
import CulturalTermPopup from '../CulturalTermPopup'

const LOCAL_PLACEHOLDER_SRC = '/local-assets/placeholder.jpg'
const CATEGORY_PRIORITY = ['food', 'heritage', 'culture', 'expression', 'lifestyle']
const WIKI_PAGE_SIZE = 20
const MASONRY_ASPECTS = ['aspect-[4/3]', 'aspect-square', 'aspect-[5/6]', 'aspect-[16/10]', 'aspect-[3/4]']

const toCategoryKey = (value) => (value || '').trim().toLowerCase()
const toLanguageKey = (value) => (value || '').trim().toLowerCase()
const toCategoryLabel = (category) => category
  .split(/[-_\s]+/)
  .filter(Boolean)
  .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
  .join(' ')

const resolveLocalImageSrc = (imageUrl) => {
  if (!imageUrl) return LOCAL_PLACEHOLDER_SRC
  if (/^https?:\/\//i.test(imageUrl)) return LOCAL_PLACEHOLDER_SRC
  if (!imageUrl.startsWith('/')) return LOCAL_PLACEHOLDER_SRC
  return imageUrl
}

const hashValue = (value) => {
  const text = String(value ?? '')
  let hash = 0
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  }
  return hash
}

const getMasonryAspectClass = (entry, index) => {
  const signature = hashValue(entry?.id || `${entry?.term || ''}-${index}`)
  return MASONRY_ASPECTS[signature % MASONRY_ASPECTS.length]
}

export default function WikiVozScreen({ apiUrl, backendUp, ttsAvailable }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [apiEntries, setApiEntries] = useState(null)   // null = not yet loaded
  const [apiError, setApiError] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedLanguage, setSelectedLanguage] = useState('all')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [visibleCount, setVisibleCount] = useState(WIKI_PAGE_SIZE)

  // Fetch all cultural terms from the API on mount
  useEffect(() => {
    let cancelled = false
    axios.get(`${apiUrl}/wiki/`, { timeout: 8000 })
      .then(({ data }) => {
        if (cancelled) return
        // Map API response to match the shape used by our cards
        const mapped = (data.results || []).map((t, i) => ({
          id: t.id || `api-${i}`,
          term: t.term,
          definition: t.definition,
          imageUrl: t.image_url || '',
          imageAlt: t.term,
          sourceUrl: '',
          language: t.language || 'Chavacano',
          category: t.category || 'heritage',
        }))
        setApiEntries(mapped.length > 0 ? mapped : null)
        setVisibleCount(WIKI_PAGE_SIZE)
      })
      .catch(() => {
        if (!cancelled) setApiError(true)
      })
    return () => { cancelled = true }
  }, [apiUrl])

  // Use API data when available, fall back to hardcoded seed data
  const allEntries = apiEntries || WIKI_VOZ_ENTRIES

  const categoryOptions = useMemo(() => {
    const discovered = new Set(
      allEntries
        .map((entry) => toCategoryKey(entry.category))
        .filter(Boolean),
    )

    const prioritized = CATEGORY_PRIORITY.filter((category) => discovered.has(category))
    const others = [...discovered].filter((category) => !CATEGORY_PRIORITY.includes(category)).sort()

    return ['all', ...prioritized, ...others]
  }, [allEntries])

  const languageOptions = useMemo(() => {
    const discovered = new Map()

    allEntries.forEach((entry) => {
      const raw = (entry.language || '').trim()
      if (!raw) return
      const key = toLanguageKey(raw)
      if (!discovered.has(key)) {
        discovered.set(key, raw)
      }
    })

    const sorted = [...discovered.entries()]
      .sort((a, b) => a[1].localeCompare(b[1]))
      .map(([key, label]) => ({ key, label }))

    return [{ key: 'all', label: 'All' }, ...sorted]
  }, [allEntries])

  const filteredEntries = useMemo(() => {
    const q = searchQuery.toLowerCase()
    return allEntries.filter((entry) => {
      const matchesCategory = selectedCategory === 'all' || toCategoryKey(entry.category) === selectedCategory
      const matchesLanguage = selectedLanguage === 'all' || toLanguageKey(entry.language) === selectedLanguage
      const matchesSearch = !q || [
        entry.term,
        entry.definition,
        entry.language,
        entry.category,
      ].some((value) => (value || '').toLowerCase().includes(q))

      return matchesCategory && matchesLanguage && matchesSearch
    })
  }, [allEntries, searchQuery, selectedCategory, selectedLanguage])

  const hasActiveFilters = selectedCategory !== 'all' || selectedLanguage !== 'all'
  const visibleEntries = filteredEntries.slice(0, visibleCount)
  const hasMoreEntries = visibleCount < filteredEntries.length

  const handleViewMore = () => {
    setVisibleCount((previous) => Math.min(previous + WIKI_PAGE_SIZE, filteredEntries.length))
  }

  const handleSearchChange = (event) => {
    setSearchQuery(event.target.value)
    setVisibleCount(WIKI_PAGE_SIZE)
  }

  const handleCategoryChange = (category) => {
    setSelectedCategory(category)
    setVisibleCount(WIKI_PAGE_SIZE)
  }

  const handleLanguageChange = (language) => {
    setSelectedLanguage(language)
    setVisibleCount(WIKI_PAGE_SIZE)
  }

  return (
    <div className="flex-1 flex flex-col px-4 sm:px-6 py-4 md:py-5 max-w-7xl mx-auto w-full">
      {/* Search Bar */}
      <div className="mb-4">
        <div className="relative w-full max-w-3xl">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary" />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Search cultural terms..."
            className="w-full bg-bg-card border border-border-subtle rounded-xl pl-12 pr-14 py-3.5 text-text-primary placeholder-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent-magenta focus:border-transparent text-base"
          />

          <button
            onClick={() => setFiltersOpen((prev) => !prev)}
            className={`absolute right-2.5 top-1/2 -translate-y-1/2 rounded-lg p-2 transition-all duration-200 ${
              filtersOpen || hasActiveFilters
                ? 'text-accent-magenta bg-accent-magenta/12'
                : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
            }`}
            title="Filter by category and language"
            aria-label="Toggle filters"
            aria-expanded={filtersOpen}
          >
            <FunnelIcon className="w-4.5 h-4.5" />
            {hasActiveFilters && (
              <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-accent-gold" />
            )}
          </button>
        </div>

        {filtersOpen && (
          <div className="animate-fade-in mt-2.5 w-full max-w-3xl rounded-xl border border-border-subtle bg-bg-card/92 p-3 backdrop-blur-sm">
            <div className="space-y-2.5">
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Categories</p>
                <div className="flex flex-wrap gap-2">
                  {categoryOptions.map((category) => (
                    <button
                      key={category}
                      onClick={() => handleCategoryChange(category)}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                        selectedCategory === category
                          ? 'bg-accent-gold text-bg-dark'
                          : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {category === 'all' ? 'All' : toCategoryLabel(category)}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">Languages</p>
                <div className="flex flex-wrap gap-2">
                  {languageOptions.map((language) => (
                    <button
                      key={language.key}
                      onClick={() => handleLanguageChange(language.key)}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                        selectedLanguage === language.key
                          ? 'bg-accent-magenta text-white'
                          : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {language.label}
                    </button>
                  ))}
                </div>
              </div>

              {hasActiveFilters && (
                <div className="flex justify-end">
                  <button
                    onClick={() => {
                      handleCategoryChange('all')
                      handleLanguageChange('all')
                    }}
                    className="rounded-full border border-accent-magenta/40 px-3 py-1.5 text-xs font-medium text-accent-magenta hover:bg-accent-magenta/10"
                  >
                    Clear filters
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Data source indicator */}
      {apiError && (
        <div className="mb-3 px-1">
          <span className="text-xs text-status-warning-text">Using offline seed data (API unavailable)</span>
        </div>
      )}

      {/* Results Count */}
      <div className="mb-3 px-1">
        <span className="text-sm text-text-secondary">
          {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'} found
          {hasActiveFilters && ' • filters active'}
        </span>
      </div>

      {/* Cultural Cards Grid (Masonry style for desktop) */}
      <div className="columns-1 sm:columns-2 xl:columns-3 2xl:columns-4 gap-4 [column-fill:balance]">
        {visibleEntries.map((entry, index) => (
          <div
            key={entry.id}
            className="mb-4 break-inside-avoid overflow-hidden rounded-xl border border-border-subtle bg-bg-card transition-all duration-200 hover:-translate-y-[1px] hover:border-accent-magenta/45 hover:shadow-lg hover:shadow-accent-magenta/8 group"
          >
            <div className={`relative ${getMasonryAspectClass(entry, index)} w-full overflow-hidden bg-bg-elevated`}>
              <img
                src={resolveLocalImageSrc(entry.imageUrl)}
                alt={entry.imageAlt || entry.term}
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                loading="lazy"
                onError={(event) => {
                  event.currentTarget.src = LOCAL_PLACEHOLDER_SRC
                }}
              />

              <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-linear-to-t from-black/80 via-black/25 to-transparent px-3.5 pb-3 pt-8">
                <div className="flex items-end justify-between gap-2">
                  <h3 className="line-clamp-2 text-base font-bold text-white sm:text-lg">{entry.term}</h3>
                  <span className="shrink-0 rounded-full bg-accent-magenta/75 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white backdrop-blur-sm">
                    {entry.language}
                  </span>
                </div>
              </div>
            </div>

            <div className="p-3">
              <button
                onClick={() => setSelectedEntry(entry)}
                className="spring-nav-transition w-full rounded-lg bg-accent-magenta px-4 py-2 text-sm font-semibold text-white hover:bg-accent-magenta/80"
              >
                View More
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredEntries.length > 0 && (
        <div className="mt-2 flex items-center justify-center">
          {hasMoreEntries ? (
            <button
              onClick={handleViewMore}
              className="spring-nav-transition rounded-xl border border-accent-magenta/45 bg-accent-magenta/10 px-4 py-2 text-sm font-semibold text-accent-magenta hover:bg-accent-magenta/20"
            >
              View More ({Math.min(WIKI_PAGE_SIZE, filteredEntries.length - visibleCount)} next)
            </button>
          ) : (
            <span className="text-xs text-text-secondary/80">You’ve reached the end of the current results.</span>
          )}
        </div>
      )}

      {/* Empty State */}
      {filteredEntries.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center py-12">
          <span className="text-4xl mb-4">🔍</span>
          <p className="text-text-secondary text-center">
            No entries found for "{searchQuery}"
          </p>
          <button
            onClick={() => setSearchQuery('')}
            className="mt-4 text-accent-magenta hover:underline text-sm"
          >
            Clear search
          </button>
        </div>
      )}

      {/* Entry Detail Popup */}
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
