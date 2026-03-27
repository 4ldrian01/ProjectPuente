/**
 * WikiVozScreen.jsx — Cultural encyclopedia screen
 * Fetches cultural terms from /api/wiki/ (PostgreSQL-backed).
 * Falls back to hardcoded wikiVozData.js seed data if API unreachable.
 * Features: Search bar, language/category filters, responsive 2-4 column grid.
 */

import { useState, useMemo, useEffect } from 'react'
import axios from 'axios'
import { SearchIcon } from '../icons/NavIcons'
import { FunnelIcon } from '../icons/NavIcons'
import { WIKI_VOZ_ENTRIES } from '../../data/wikiVozData'
import CulturalTermPopup from '../CulturalTermPopup'

export default function WikiVozScreen({ apiUrl, backendUp, ttsAvailable }) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [apiEntries, setApiEntries] = useState(null)   // null = not yet loaded
  const [apiError, setApiError] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [selectedLanguage, setSelectedLanguage] = useState('all')
  const [selectedCategory, setSelectedCategory] = useState('all')

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
          category: t.category || '',
        }))
        setApiEntries(mapped.length > 0 ? mapped : null)
      })
      .catch(() => {
        if (!cancelled) setApiError(true)
      })
    return () => { cancelled = true }
  }, [apiUrl])

  // Use API data when available, fall back to hardcoded seed data
  const allEntries = apiEntries || WIKI_VOZ_ENTRIES

  const languageOptions = useMemo(() => {
    return ['all', ...new Set(allEntries.map((entry) => entry.language).filter(Boolean))]
  }, [allEntries])

  const categoryOptions = useMemo(() => {
    return ['all', ...new Set(allEntries.map((entry) => entry.category).filter(Boolean))]
  }, [allEntries])

  const filteredEntries = useMemo(() => {
    const q = searchQuery.toLowerCase()
    return allEntries.filter((entry) => {
      const matchesLanguage = selectedLanguage === 'all' || entry.language === selectedLanguage
      const matchesCategory = selectedCategory === 'all' || entry.category === selectedCategory
      const matchesSearch = !q || [
        entry.term,
        entry.definition,
        entry.language,
        entry.category,
      ].some((value) => (value || '').toLowerCase().includes(q))

      return matchesLanguage && matchesCategory && matchesSearch
    })
  }, [allEntries, searchQuery, selectedCategory, selectedLanguage])

  const hasActiveFilters = selectedLanguage !== 'all' || selectedCategory !== 'all'

  return (
    <div className="flex-1 flex flex-col px-4 sm:px-6 py-4 md:py-6 max-w-6xl mx-auto w-full">
      {/* Search Bar */}
      <div className="mb-4 max-w-4xl">
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-2xl">
            <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search cultural terms..."
              className="w-full bg-bg-card border border-border-subtle rounded-xl pl-12 pr-4 py-3.5 text-text-primary placeholder-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent-magenta focus:border-transparent text-base"
            />
          </div>

          <button
            onClick={() => setShowFilters((prev) => !prev)}
            className={`shrink-0 inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium transition-colors ${
              showFilters || hasActiveFilters
                ? 'border-accent-magenta bg-accent-magenta/10 text-accent-magenta'
                : 'border-border-subtle bg-bg-card text-text-secondary hover:text-text-primary'
            }`}
            aria-expanded={showFilters}
            aria-label="Toggle filters"
          >
            <FunnelIcon className="w-4.5 h-4.5" />
            Filter
          </button>
        </div>

        {showFilters && (
          <div className="mt-3 rounded-2xl border border-border-subtle bg-bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">Language</p>
                <div className="flex flex-wrap gap-2">
                  {languageOptions.map((language) => (
                    <button
                      key={language}
                      onClick={() => setSelectedLanguage(language)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                        selectedLanguage === language
                          ? 'bg-accent-magenta text-white'
                          : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {language === 'all' ? 'All languages' : language}
                    </button>
                  ))}
                </div>
              </div>

              <div className="min-w-0 flex-1">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">Category</p>
                <div className="flex flex-wrap gap-2">
                  {categoryOptions.map((category) => (
                    <button
                      key={category}
                      onClick={() => setSelectedCategory(category)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                        selectedCategory === category
                          ? 'bg-accent-gold text-bg-dark'
                          : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {category === 'all' ? 'All categories' : category}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={() => {
                  setSelectedLanguage('all')
                  setSelectedCategory('all')
                }}
                className="text-xs font-medium text-accent-magenta hover:underline"
              >
                Clear filters
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Data source indicator */}
      {apiError && (
        <div className="mb-3 px-1">
          <span className="text-xs text-amber-400">Using offline seed data (API unavailable)</span>
        </div>
      )}

      {/* Results Count */}
      <div className="mb-4 px-1">
        <span className="text-sm text-text-secondary">
          {filteredEntries.length} {filteredEntries.length === 1 ? 'entry' : 'entries'} found
          {hasActiveFilters && ' • filters active'}
        </span>
      </div>

      {/* Cultural Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 md:gap-5">
        {filteredEntries.map((entry) => (
          <div
            key={entry.id}
            className="bg-bg-card border border-border-subtle rounded-xl overflow-hidden hover:border-accent-magenta/50 transition-all duration-200 hover:shadow-lg hover:shadow-accent-magenta/5 group"
          >
            {/* Image */}
            <div className="aspect-square w-full overflow-hidden bg-bg-elevated">
              {entry.imageUrl ? (
                <img
                  src={entry.imageUrl}
                  alt={entry.imageAlt || entry.term}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  onError={(e) => {
                    e.target.style.display = 'none'
                  }}
                />
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center px-4 text-center text-text-secondary/70">
                  <span className="mb-2 text-2xl">🖼️</span>
                  <span className="text-xs uppercase tracking-wider">Image placeholder</span>
                </div>
              )}
            </div>

            {/* Content */}
            <div className="p-3 md:p-4">
              <h3 className="font-bold text-text-primary text-base md:text-lg mb-1 truncate">
                {entry.term}
              </h3>
              <span className="inline-block text-xs bg-accent-magenta/20 text-accent-magenta px-2 py-0.5 rounded-full mb-3">
                {entry.language}
              </span>
              
              <button
                onClick={() => setSelectedEntry(entry)}
                className="w-full bg-accent-magenta hover:bg-accent-magenta/80 text-white font-medium py-2 px-4 rounded-lg transition-colors text-sm"
              >
                View
              </button>
            </div>
          </div>
        ))}
      </div>

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
