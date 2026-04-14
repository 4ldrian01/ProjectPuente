/**
 * DatabaseAdminScreen.jsx — God Mode database operations panel.
 *
 * Live CRUD surface for CulturalTerm management via /api/wiki/.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { Database, FileUp, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import {
  CATEGORY_OPTIONS,
  LANGUAGE_LABEL_BY_CODE,
  LANGUAGE_OPTIONS,
  mapWikiVozArrayToAdminRecords,
  parseCsvTextToWikiVozArray,
  parseJsonTextToWikiVozArray,
  toTriggerWordsArray,
} from '../../lib/dbAdminImport'
import { withApiKeyHeaders } from '../../lib/apiAuth'

const DEFAULT_FORM = {
  term: '',
  language: 'Chavacano',
  category: 'Idioms',
  triggerWords: '',
  definition: '',
}

const ADMIN_BATCH_SIZE = 20

function extractApiMessage(error, fallbackMessage) {
  const payload = error?.response?.data
  if (payload && typeof payload === 'object') {
    const direct = String(payload.error || '').trim()
    if (direct) return direct

    const details = payload.details
    if (details && typeof details === 'object') {
      const flattened = Object.values(details)
        .flat()
        .map((entry) => String(entry || '').trim())
        .filter(Boolean)
        .join(' ')
      if (flattened) return flattened
    }
  }

  return fallbackMessage
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase()
}

function isEditableTarget(target) {
  return target instanceof HTMLElement && (
    target.tagName === 'INPUT'
    || target.tagName === 'TEXTAREA'
    || target.tagName === 'SELECT'
    || target.isContentEditable
  )
}

export default function DatabaseAdminScreen({ apiUrl, notify }) {
  const rootRef = useRef(null)
  const fileInputRef = useRef(null)
  const appendTimerRef = useRef(null)

  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [importing, setImporting] = useState(false)
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [languageFilter, setLanguageFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [visibleCount, setVisibleCount] = useState(ADMIN_BATCH_SIZE)
  const [isAppending, setIsAppending] = useState(false)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingRecordId, setEditingRecordId] = useState(null)
  const [form, setForm] = useState(DEFAULT_FORM)

  const emitToast = useMemo(() => {
    if (typeof notify !== 'function') {
      return () => {}
    }

    return notify
  }, [notify])

  const fetchWikiRecords = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true)
    }
    setNotice('')

    try {
      const { data } = await axios.get(`${apiUrl}/wiki/`, {
        timeout: 8000,
        headers: withApiKeyHeaders(),
      })

      const payloadRows = Array.isArray(data?.results)
        ? data.results
        : (Array.isArray(data?.wiki_voz_entries) ? data.wiki_voz_entries : [])

      const mapped = mapWikiVozArrayToAdminRecords(payloadRows, 'api')
      setRecords(mapped)

      if (mapped.length === 0) {
        setNotice('No wiki records found in the database yet.')
      }
      return mapped
    } catch (error) {
      setRecords([])
      const message = extractApiMessage(error, 'Failed to load wiki records from API.')
      setNotice(message)
      emitToast({
        title: 'Wiki fetch failed',
        message,
        variant: 'error',
        durationMs: 4200,
      })
      return []
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }, [apiUrl, emitToast])

  useEffect(() => {
    let cancelled = false

    fetchWikiRecords().catch(() => {
      if (!cancelled) {
        setLoading(false)
      }
    })

    return () => {
      cancelled = true
    }
  }, [fetchWikiRecords])

  useEffect(() => {
    if (!notice) return undefined

    const timer = setTimeout(() => setNotice(''), 2800)
    return () => clearTimeout(timer)
  }, [notice])

  const filteredRecords = useMemo(() => {
    const normalizedQuery = normalizeText(query)

    return records.filter((record) => {
      const matchesLanguage = languageFilter === 'all' || record.language === languageFilter
      const matchesCategory = categoryFilter === 'all' || record.category === categoryFilter

      if (!matchesLanguage || !matchesCategory) {
        return false
      }

      if (!normalizedQuery) {
        return true
      }

      return [
        record.term,
        record.definition,
        record.language,
        record.category,
        (record.trigger_words || []).join(' '),
      ].some((field) => normalizeText(field).includes(normalizedQuery))
    })
  }, [categoryFilter, languageFilter, query, records])

  useEffect(() => {
    setVisibleCount(ADMIN_BATCH_SIZE)
  }, [query, languageFilter, categoryFilter])

  useEffect(() => {
    setVisibleCount((previous) => {
      if (filteredRecords.length === 0) {
        return ADMIN_BATCH_SIZE
      }

      return Math.max(ADMIN_BATCH_SIZE, Math.min(previous, filteredRecords.length))
    })
  }, [filteredRecords.length])

  const visibleRecords = useMemo(
    () => filteredRecords.slice(0, visibleCount),
    [filteredRecords, visibleCount],
  )

  const hasMoreRecords = visibleRecords.length < filteredRecords.length
  const visibleRangeStart = filteredRecords.length === 0 ? 0 : 1
  const visibleRangeEnd = visibleRecords.length

  const categoryFilterOptions = useMemo(() => (
    CATEGORY_OPTIONS.filter((category) => records.some((record) => record.category === category))
  ), [records])

  const openCreateModal = () => {
    setEditingRecordId(null)
    setForm(DEFAULT_FORM)
    setIsModalOpen(true)
  }

  const openEditModal = (record) => {
    setEditingRecordId(record.id)
    setForm({
      term: record.term,
      language: record.language,
      category: record.category,
      triggerWords: (record.trigger_words || []).join(', '),
      definition: record.definition,
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingRecordId(null)
    setForm(DEFAULT_FORM)
  }

  const handleSaveRecord = async () => {
    const nextTerm = form.term.trim()
    const nextTriggerWords = toTriggerWordsArray(form.triggerWords)
    const nextDefinition = form.definition.trim()

    if (!nextTerm || !nextDefinition || nextTriggerWords.length === 0) {
      setNotice('Term, trigger words, and definition are required before saving.')
      emitToast({
        title: 'Validation required',
        message: 'Term, trigger words, and definition are required before saving.',
        variant: 'warning',
        durationMs: 3600,
      })
      return
    }

    setSubmitting(true)

    try {
      const payload = {
        term: nextTerm,
        definition: nextDefinition,
        trigger_words: nextTriggerWords,
        language: form.language,
        category: form.category,
      }

      if (editingRecordId !== null && editingRecordId !== undefined) {
        payload.id = editingRecordId
      }

      const { data } = await axios.post(`${apiUrl}/wiki/`, payload, {
        timeout: 10000,
        headers: withApiKeyHeaders(),
      })

      const mapped = mapWikiVozArrayToAdminRecords([data], 'api-write')[0]

      if (mapped) {
        setRecords((previous) => {
          const filtered = previous.filter((record) => String(record.id) !== String(mapped.id))
          return [mapped, ...filtered]
        })
      } else {
        await fetchWikiRecords({ silent: true })
      }

      setNotice(editingRecordId ? 'Record updated in database.' : 'New record added to database.')
      emitToast({
        title: editingRecordId ? 'Record updated' : 'Record created',
        message: `${nextTerm} synced to SQLite via API.`,
        variant: 'success',
        durationMs: 3200,
      })
      closeModal()
    } catch (error) {
      const message = extractApiMessage(
        error,
        editingRecordId
          ? 'Failed to update record via API.'
          : 'Failed to create record via API.',
      )
      setNotice(message)
      emitToast({
        title: 'Save failed',
        message,
        variant: 'error',
        durationMs: 4200,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleDeleteRecord = async (recordId) => {
    setDeletingId(recordId)
    try {
      await axios.delete(`${apiUrl}/wiki/`, {
        timeout: 10000,
        headers: withApiKeyHeaders(),
        params: { id: recordId },
      })

      setRecords((previous) => previous.filter((record) => String(record.id) !== String(recordId)))
      setNotice('Record deleted from database.')
      emitToast({
        title: 'Record deleted',
        message: 'The selected wiki term was removed from SQLite.',
        variant: 'info',
        durationMs: 3200,
      })
    } catch (error) {
      const message = extractApiMessage(error, 'Failed to delete wiki record.')
      setNotice(message)
      emitToast({
        title: 'Delete failed',
        message,
        variant: 'error',
        durationMs: 4200,
      })
    } finally {
      setDeletingId(null)
    }
  }

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleImportFile = async (event) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    try {
      setImporting(true)
      const importText = await file.text()
      const filename = String(file.name || '').toLowerCase()
      const isJson = filename.endsWith('.json') || file.type.includes('json')
      const parsedRows = isJson
        ? parseJsonTextToWikiVozArray(importText)
        : parseCsvTextToWikiVozArray(importText)
      const imported = mapWikiVozArrayToAdminRecords(parsedRows, isJson ? 'json-import' : 'csv-import')

      if (imported.length === 0) {
        setNotice('Import failed: expected id, trigger_words, language, category, title, description.')
        emitToast({
          title: 'Import failed',
          message: 'Expected schema: id, trigger_words, language, category, title, description.',
          variant: 'error',
          durationMs: 4600,
        })
        return
      }

      let successCount = 0
      let failureCount = 0

      for (const row of imported) {
        const payload = {
          term: row.term,
          definition: row.definition,
          trigger_words: row.trigger_words,
          language: row.language,
          category: row.category,
        }

        try {
          await axios.post(`${apiUrl}/wiki/`, payload, {
            timeout: 10000,
            headers: withApiKeyHeaders(),
          })
          successCount += 1
        } catch {
          failureCount += 1
        }
      }

      await fetchWikiRecords({ silent: true })
      setNotice(`Imported ${successCount}/${imported.length} rows into SQLite.`)
      emitToast({
        title: 'Import complete',
        message: failureCount > 0
          ? `${successCount} imported, ${failureCount} failed.`
          : `Imported ${successCount} ${isJson ? 'JSON' : 'CSV'} records into SQLite.`,
        variant: failureCount > 0 ? 'warning' : 'success',
        durationMs: 4200,
      })
    } catch {
      setNotice('Import failed in this browser context.')
      emitToast({
        title: 'Import failed',
        message: 'Import failed in this browser context.',
        variant: 'error',
        durationMs: 4200,
      })
    } finally {
      setImporting(false)
      event.target.value = ''
    }
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

  const handleShowMore = useCallback(() => {
    if (!hasMoreRecords) {
      return
    }

    runAppendTransition((previous) => Math.min(filteredRecords.length, previous + ADMIN_BATCH_SIZE))
  }, [filteredRecords.length, hasMoreRecords, runAppendTransition])

  const handleShowAll = useCallback(() => {
    if (!hasMoreRecords) {
      return
    }

    runAppendTransition(() => filteredRecords.length)
  }, [filteredRecords.length, hasMoreRecords, runAppendTransition])

  const handleResetToFirstBatch = useCallback(() => {
    clearAppendTimer()
    setIsAppending(false)
    setVisibleCount(ADMIN_BATCH_SIZE)
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

      if (isModalOpen) {
        return
      }

      const rootElement = rootRef.current
      if (!rootElement || rootElement.offsetParent === null) {
        return
      }

      if ((event.key === ']' || event.key === 'ArrowRight') && hasMoreRecords) {
        event.preventDefault()
        handleShowMore()
        return
      }

      if (event.key === 'End' && hasMoreRecords) {
        event.preventDefault()
        handleShowAll()
        return
      }

      if (event.key === 'Home' && visibleRecords.length > ADMIN_BATCH_SIZE) {
        event.preventDefault()
        handleResetToFirstBatch()
      }
    }

    window.addEventListener('keydown', handlePaginationShortcuts)
    return () => {
      window.removeEventListener('keydown', handlePaginationShortcuts)
    }
  }, [handleResetToFirstBatch, handleShowAll, handleShowMore, hasMoreRecords, isModalOpen, visibleRecords.length])

  return (
    <div ref={rootRef} className="mx-auto w-full max-w-7xl space-y-6">
      <header className="a26-surface relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -right-12 top-2 h-32 w-32 rounded-full bg-accent-magenta/10 blur-3xl" />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="a26-subtitle">God Mode</p>
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Database Admin</h2>
            <p className="mt-1 text-sm text-text-secondary">ML sociolinguistic interceptor patches for strict linguistic gap coverage.</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleImportClick}
              disabled={importing}
              className="a26-button-ghost inline-flex items-center gap-1.5 px-3 py-2 text-sm font-semibold"
            >
              <FileUp className="h-4 w-4" />
              {importing ? 'Importing...' : 'Import CSV / JSON'}
            </button>

            <button
              onClick={openCreateModal}
              disabled={submitting}
              className="a26-button-primary inline-flex items-center gap-1.5 px-3 py-2 text-sm font-semibold"
            >
              <Plus className="h-4 w-4" />
              Add New Term
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.json,text/csv,application/json"
          className="hidden"
          onChange={handleImportFile}
        />
      </header>

      <section className="a26-surface p-4 md:p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search term, trigger words, definition, category..."
              className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 py-2.5 pl-9 pr-3 text-sm text-text-primary placeholder-text-secondary/60 transition-all duration-300 focus:border-accent-magenta/70 focus:outline-none"
            />
          </div>

          <select
            value={languageFilter}
            onChange={(event) => setLanguageFilter(event.target.value)}
            className="rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2.5 text-sm text-text-primary transition-all duration-300 focus:border-accent-magenta/70 focus:outline-none"
          >
            <option value="all">All Languages</option>
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>

          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            className="rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2.5 text-sm text-text-primary transition-all duration-300 focus:border-accent-magenta/70 focus:outline-none"
          >
            <option value="all">All Categories</option>
            {categoryFilterOptions.map((category) => (
              <option key={category} value={category}>{category}</option>
            ))}
          </select>
        </div>

        {notice && (
          <div className="mb-3 rounded-xl border border-status-info-border/55 bg-status-info-bg/80 px-3 py-2 text-xs text-status-info-text">
            {notice}
          </div>
        )}

        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border-subtle/75 bg-bg-card/55 px-3 py-2 text-sm text-text-secondary">
          <span>
            Showing {visibleRangeStart}-{visibleRangeEnd} of {filteredRecords.length} filtered records
          </span>
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide">
            <span className="a26-chip">{records.length} total</span>
            <span className="a26-chip">Batch {ADMIN_BATCH_SIZE}</span>
          </div>
        </div>

        <div className={`overflow-hidden rounded-2xl border border-border-subtle/80 ${isAppending ? 'a26-list-appending' : ''}`} aria-busy={isAppending}>
          <div className="max-h-[430px] overflow-auto">
            <table className="min-w-full divide-y divide-border-subtle text-sm">
              <thead className="sticky top-0 z-10 bg-bg-elevated/95 backdrop-blur-sm">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Term</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Language</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Category</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Trigger Words</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Definition</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-text-secondary">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border-subtle bg-bg-card">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-text-secondary">Loading records from API...</td>
                  </tr>
                ) : filteredRecords.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-text-secondary">No wiki records match the current filters.</td>
                  </tr>
                ) : (
                  visibleRecords.map((record) => (
                    <tr key={record.id} className="transition-colors duration-200 hover:bg-bg-elevated/55">
                      <td className="px-3 py-2 font-semibold text-text-primary">{record.term}</td>
                      <td className="px-3 py-2 text-text-secondary">{LANGUAGE_LABEL_BY_CODE[record.language] || record.language}</td>
                      <td className="px-3 py-2 text-text-secondary">{record.category}</td>
                      <td className="max-w-[280px] px-3 py-2 text-text-secondary">
                        <div className="flex flex-wrap gap-1">
                          {(record.trigger_words || []).map((triggerWord) => (
                            <span
                              key={`${record.id}-${triggerWord}`}
                              className="rounded-full border border-border-subtle bg-bg-elevated/70 px-2 py-0.5 text-xs"
                            >
                              {triggerWord}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="max-w-[360px] px-3 py-2 text-text-secondary">
                        <p className="line-clamp-2">{record.definition}</p>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => openEditModal(record)}
                            className="rounded-xl border border-border-subtle p-1.5 text-text-secondary transition-all duration-200 hover:border-accent-magenta/55 hover:text-accent-magenta active:scale-[0.98]"
                            title="Edit record"
                          >
                            <Pencil className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteRecord(record.id)}
                            disabled={deletingId === record.id}
                            className="rounded-xl border border-border-subtle p-1.5 text-text-secondary transition-all duration-200 hover:border-status-danger-border hover:text-status-danger-text active:scale-[0.98]"
                            title="Delete record"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {!loading && filteredRecords.length > 0 ? (
          <div className="mt-3 flex flex-col gap-2 rounded-xl border border-border-subtle/75 bg-bg-card/45 px-3 py-2.5 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
            <span className="text-xs sm:text-sm" aria-live="polite">
              Displaying {visibleRangeStart}-{visibleRangeEnd} of {filteredRecords.length} records
            </span>

            <div className="flex flex-wrap items-center justify-end gap-2">
              <span className="a26-pagination-hint">
                Shortcuts: ] / Right Arrow = +20, End = all, Home = first 20
              </span>

              {hasMoreRecords ? (
                <button
                  type="button"
                  onClick={handleShowMore}
                  disabled={isAppending}
                  className="a26-button-primary px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-60"
                  aria-keyshortcuts="] ArrowRight"
                  title="Shortcut: ] or Right Arrow"
                >
                  {isAppending ? 'Loading...' : 'Show 20 More'}
                </button>
              ) : null}

              {hasMoreRecords ? (
                <button
                  type="button"
                  onClick={handleShowAll}
                  disabled={isAppending}
                  className="a26-button-ghost px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-60"
                  aria-keyshortcuts="End"
                  title="Shortcut: End"
                >
                  Show All
                </button>
              ) : null}

              {visibleRecords.length > ADMIN_BATCH_SIZE ? (
                <button
                  type="button"
                  onClick={handleResetToFirstBatch}
                  disabled={isAppending}
                  className="a26-button-ghost px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-60"
                  aria-keyshortcuts="Home"
                  title="Shortcut: Home"
                >
                  Reset To First 20
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-overlay-scrim/65 backdrop-blur-sm" onClick={closeModal} />

          <div className="a26-surface relative z-10 w-full max-w-xl p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="inline-flex items-center gap-2">
                <Database className="h-4 w-4 text-accent-magenta" />
                <h3 className="text-lg font-semibold text-text-primary">
                  {editingRecordId ? 'Edit Wiki Term' : 'Add Wiki Term'}
                </h3>
              </div>

              <button
                onClick={closeModal}
                className="a26-button-ghost p-1"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Term / Title</label>
                <input
                  value={form.term}
                  onChange={(event) => setForm((previous) => ({ ...previous, term: event.target.value }))}
                  className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  placeholder="Enter linguistic gap term"
                />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Language</label>
                  <select
                    value={form.language}
                    onChange={(event) => setForm((previous) => ({ ...previous, language: event.target.value }))}
                    className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  >
                    {LANGUAGE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Category</label>
                  <select
                    value={form.category}
                    onChange={(event) => setForm((previous) => ({ ...previous, category: event.target.value }))}
                    className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  >
                    {CATEGORY_OPTIONS.map((category) => (
                      <option key={category} value={category}>{category}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Trigger Words</label>
                <input
                  value={form.triggerWords}
                  onChange={(event) => setForm((previous) => ({ ...previous, triggerWords: event.target.value }))}
                  className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  placeholder="Comma-separated triggers, e.g. rompe cabeza, rompecabeza"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Definition / Sociolinguistic Patch</label>
                <textarea
                  value={form.definition}
                  onChange={(event) => setForm((previous) => ({ ...previous, definition: event.target.value }))}
                  rows={4}
                  className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  placeholder="Describe the strict sociolinguistic correction to apply"
                />
              </div>
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={closeModal}
                disabled={submitting}
                className="a26-button-ghost px-3 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRecord}
                disabled={submitting}
                className="a26-button-primary px-3 py-2 text-sm font-semibold"
              >
                {submitting ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
