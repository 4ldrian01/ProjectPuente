/**
 * DatabaseAdminScreen.jsx — God Mode database operations panel.
 *
 * Mock CRUD surface for CulturalTerm management.
 * Uses local state mutations for UI workflow validation.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { Database, FileUp, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import { WIKI_VOZ_ENTRIES } from '../../data/wikiVozData'

const LANGUAGE_OPTIONS = [
  { value: 'cbk', label: 'Chavacano (cbk)' },
  { value: 'ceb', label: 'Cebuano/Bisaya (ceb)' },
  { value: 'hil', label: 'Hiligaynon (hil)' },
  { value: 'es', label: 'Spanish (es)' },
  { value: 'tl', label: 'Tagalog (tl)' },
]

const CATEGORY_OPTIONS = [
  'food',
  'culture',
  'heritage',
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
]

const DEFAULT_FORM = {
  term: '',
  language: 'cbk',
  category: 'culture',
  definition: '',
}

function normalizeText(value) {
  return String(value || '').trim().toLowerCase()
}

function inferLanguageCode(languageValue) {
  const normalized = normalizeText(languageValue)

  if (normalized.includes('chavacano') || normalized === 'cbk') return 'cbk'
  if (normalized.includes('hiligaynon') || normalized.includes('ilonggo') || normalized === 'hil') return 'hil'
  if (normalized.includes('cebuano') || normalized.includes('bisaya') || normalized === 'ceb') return 'ceb'
  if (normalized.includes('tagalog') || normalized.includes('filipino') || normalized === 'tl') return 'tl'
  if (normalized.includes('spanish') || normalized === 'es') return 'es'

  return 'cbk'
}

function mapApiRecord(entry, index) {
  return {
    id: String(entry.id || `api-${index}`),
    term: entry.term || '',
    language: inferLanguageCode(entry.language),
    category: String(entry.category || 'culture').trim().toLowerCase(),
    definition: entry.definition || '',
    updatedAt: new Date().toISOString(),
    source: 'api',
  }
}

function mapFallbackRecord(entry, index) {
  return {
    id: String(entry.id || `fallback-${index}`),
    term: entry.term || '',
    language: inferLanguageCode(entry.language),
    category: String(entry.category || 'culture').trim().toLowerCase(),
    definition: entry.definition || '',
    updatedAt: new Date().toISOString(),
    source: 'fallback',
  }
}

function parseCsvRows(csvText) {
  const lines = String(csvText || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length === 0) {
    return []
  }

  const header = lines[0].split(',').map((cell) => normalizeText(cell))
  const termIndex = header.indexOf('term')
  const languageIndex = header.indexOf('language')
  const categoryIndex = header.indexOf('category')
  const definitionIndex = header.indexOf('definition')

  if (termIndex < 0 || definitionIndex < 0) {
    return []
  }

  const dataRows = []

  for (let i = 1; i < lines.length; i += 1) {
    const columns = lines[i].split(',').map((cell) => cell.trim())
    const term = columns[termIndex] || ''
    const definition = columns[definitionIndex] || ''

    if (!term || !definition) {
      continue
    }

    dataRows.push({
      term,
      definition,
      language: inferLanguageCode(columns[languageIndex] || 'cbk'),
      category: normalizeText(columns[categoryIndex] || 'culture') || 'culture',
    })
  }

  return dataRows
}

function formatTimestamp(isoValue) {
  if (!isoValue) return '-'

  try {
    return new Date(isoValue).toLocaleString()
  } catch {
    return '-'
  }
}

export default function DatabaseAdminScreen({ apiUrl, notify }) {
  const fileInputRef = useRef(null)

  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [languageFilter, setLanguageFilter] = useState('all')

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingRecordId, setEditingRecordId] = useState(null)
  const [form, setForm] = useState(DEFAULT_FORM)

  const emitToast = useMemo(() => {
    if (typeof notify !== 'function') {
      return () => {}
    }

    return notify
  }, [notify])

  useEffect(() => {
    let cancelled = false

    const hydrateRecords = async () => {
      setLoading(true)
      setNotice('')

      try {
        const { data } = await axios.get(`${apiUrl}/wiki/`, { timeout: 8000 })
        if (cancelled) return

        const mapped = (data?.results || []).map((entry, index) => mapApiRecord(entry, index))
        setRecords(mapped)

        if (mapped.length === 0) {
          setNotice('No API rows returned. Use + Add New Term or Import CSV to seed records.')
        }
      } catch {
        if (cancelled) return

        const fallback = WIKI_VOZ_ENTRIES.slice(0, 60).map((entry, index) => mapFallbackRecord(entry, index))
        setRecords(fallback)
        setNotice('API unavailable. Loaded offline fallback records for admin workflow.')
        emitToast({
          title: 'API fallback loaded',
          message: 'Database admin is running in offline fallback mode.',
          variant: 'warning',
          durationMs: 4200,
        })
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    hydrateRecords()

    return () => {
      cancelled = true
    }
  }, [apiUrl, emitToast])

  useEffect(() => {
    if (!notice) return undefined

    const timer = setTimeout(() => setNotice(''), 2800)
    return () => clearTimeout(timer)
  }, [notice])

  const filteredRecords = useMemo(() => {
    const normalizedQuery = normalizeText(query)

    return records.filter((record) => {
      const matchesLanguage = languageFilter === 'all' || record.language === languageFilter

      if (!matchesLanguage) {
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
      ].some((field) => normalizeText(field).includes(normalizedQuery))
    })
  }, [languageFilter, query, records])

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
      definition: record.definition,
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingRecordId(null)
    setForm(DEFAULT_FORM)
  }

  const handleSaveRecord = () => {
    const nextTerm = form.term.trim()
    const nextDefinition = form.definition.trim()

    if (!nextTerm || !nextDefinition) {
      setNotice('Term and definition are required before saving.')
      emitToast({
        title: 'Validation required',
        message: 'Term and definition are required before saving.',
        variant: 'warning',
        durationMs: 3600,
      })
      return
    }

    if (editingRecordId) {
      setRecords((previous) => previous.map((record) => (
        record.id === editingRecordId
          ? {
              ...record,
              term: nextTerm,
              language: form.language,
              category: form.category,
              definition: nextDefinition,
              updatedAt: new Date().toISOString(),
              source: 'local-edit',
            }
          : record
      )))
      setNotice('Record updated (mock local state).')
      emitToast({ title: 'Record updated', message: `${nextTerm} was updated locally.`, variant: 'success', durationMs: 3200 })
    } else {
      const newRecord = {
        id: `local-${Date.now()}`,
        term: nextTerm,
        language: form.language,
        category: form.category,
        definition: nextDefinition,
        updatedAt: new Date().toISOString(),
        source: 'local-new',
      }

      setRecords((previous) => [newRecord, ...previous])
      setNotice('New record created (mock local state).')
      emitToast({ title: 'Record created', message: `${nextTerm} was added locally.`, variant: 'success', durationMs: 3200 })
    }

    closeModal()
  }

  const handleDeleteRecord = (recordId) => {
    setRecords((previous) => previous.filter((record) => record.id !== recordId))
    setNotice('Record removed from local table.')
    emitToast({ title: 'Record removed', message: 'The selected row was removed from local state.', variant: 'info', durationMs: 3200 })
  }

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleImportCsv = async (event) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    try {
      const csvText = await file.text()
      const rows = parseCsvRows(csvText)

      if (rows.length === 0) {
        setNotice('CSV import failed: expected columns term, definition, language, category.')
        emitToast({
          title: 'Import failed',
          message: 'Expected CSV columns: term, definition, language, category.',
          variant: 'error',
          durationMs: 4600,
        })
        return
      }

      const imported = rows.map((row, index) => ({
        id: `import-${Date.now()}-${index}`,
        term: row.term,
        language: row.language,
        category: row.category,
        definition: row.definition,
        updatedAt: new Date().toISOString(),
        source: 'csv-import',
      }))

      setRecords((previous) => [...imported, ...previous])
      setNotice(`Imported ${imported.length} rows from CSV (mock ingest).`)
      emitToast({
        title: 'Import complete',
        message: `Imported ${imported.length} rows into local table state.`,
        variant: 'success',
        durationMs: 3600,
      })
    } catch {
      setNotice('CSV import failed in this browser context.')
      emitToast({
        title: 'Import failed',
        message: 'CSV import failed in this browser context.',
        variant: 'error',
        durationMs: 4200,
      })
    } finally {
      event.target.value = ''
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="a26-surface relative overflow-hidden p-5 md:p-6">
        <div className="pointer-events-none absolute -right-12 top-2 h-32 w-32 rounded-full bg-accent-magenta/10 blur-3xl" />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="a26-subtitle">God Mode</p>
            <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">Database Admin</h2>
            <p className="mt-1 text-sm text-text-secondary">Mock CRUD console for CulturalTerm records.</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleImportClick}
              className="a26-button-ghost inline-flex items-center gap-1.5 px-3 py-2 text-sm font-semibold"
            >
              <FileUp className="h-4 w-4" />
              📤 Import CSV
            </button>

            <button
              onClick={openCreateModal}
              className="a26-button-primary inline-flex items-center gap-1.5 px-3 py-2 text-sm font-semibold"
            >
              <Plus className="h-4 w-4" />
              + Add New Term
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={handleImportCsv}
        />
      </header>

      <section className="a26-surface p-4 md:p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search term, definition, category..."
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
        </div>

        {notice && (
          <div className="mb-3 rounded-xl border border-status-info-border/55 bg-status-info-bg/80 px-3 py-2 text-xs text-status-info-text">
            {notice}
          </div>
        )}

        <div className="overflow-hidden rounded-2xl border border-border-subtle/80">
          <div className="max-h-[430px] overflow-auto">
            <table className="min-w-full divide-y divide-border-subtle text-sm">
              <thead className="sticky top-0 z-10 bg-bg-elevated/95 backdrop-blur-sm">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Term</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Language</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Category</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Definition</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">Updated</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wide text-text-secondary">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-border-subtle bg-bg-card">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-text-secondary">Loading records…</td>
                  </tr>
                ) : filteredRecords.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-text-secondary">No records match the current filters.</td>
                  </tr>
                ) : (
                  filteredRecords.map((record) => (
                    <tr key={record.id} className="transition-colors duration-200 hover:bg-bg-elevated/55">
                      <td className="px-3 py-2 font-semibold text-text-primary">{record.term}</td>
                      <td className="px-3 py-2 text-text-secondary">{record.language}</td>
                      <td className="px-3 py-2 text-text-secondary">{record.category}</td>
                      <td className="max-w-[360px] px-3 py-2 text-text-secondary">
                        <p className="line-clamp-2">{record.definition}</p>
                      </td>
                      <td className="px-3 py-2 text-xs text-text-secondary">{formatTimestamp(record.updatedAt)}</td>
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
      </section>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-overlay-scrim/65 backdrop-blur-sm" onClick={closeModal} />

          <div className="a26-surface relative z-10 w-full max-w-xl p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="inline-flex items-center gap-2">
                <Database className="h-4 w-4 text-accent-magenta" />
                <h3 className="text-lg font-semibold text-text-primary">
                  {editingRecordId ? 'Edit CulturalTerm' : 'Add CulturalTerm'}
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
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Term</label>
                <input
                  value={form.term}
                  onChange={(event) => setForm((previous) => ({ ...previous, term: event.target.value }))}
                  className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  placeholder="Enter term"
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
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-text-secondary">Definition</label>
                <textarea
                  value={form.definition}
                  onChange={(event) => setForm((previous) => ({ ...previous, definition: event.target.value }))}
                  rows={4}
                  className="w-full rounded-xl border border-border-subtle bg-bg-elevated/60 px-3 py-2 text-sm text-text-primary focus:border-accent-magenta/70 focus:outline-none"
                  placeholder="Describe the term context and sociolinguistic meaning"
                />
              </div>
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                onClick={closeModal}
                className="a26-button-ghost px-3 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRecord}
                className="a26-button-primary px-3 py-2 text-sm font-semibold"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
