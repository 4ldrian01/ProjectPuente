const LANGUAGE_OPTION_ROWS = [
  ['Chavacano', 'Chavacano'],
  ['Cebuano/Bisaya', 'Cebuano/Bisaya'],
  ['Hiligaynon', 'Hiligaynon'],
  ['Spanish', 'Spanish'],
]

export const LANGUAGE_OPTIONS = LANGUAGE_OPTION_ROWS.map(([value, label]) => ({ value, label }))

export const LANGUAGE_LABEL_BY_CODE = {
  Chavacano: 'Chavacano',
  'Cebuano/Bisaya': 'Cebuano/Bisaya',
  Hiligaynon: 'Hiligaynon',
  Spanish: 'Spanish',
  cbk: 'Chavacano',
  ceb: 'Cebuano/Bisaya',
  hil: 'Hiligaynon',
  es: 'Spanish',
}

const LANGUAGE_ALIAS_TO_CANONICAL = new Map([
  ['cbk', 'Chavacano'],
  ['chavacano', 'Chavacano'],
  ['chavacano (zamboanga)', 'Chavacano'],
  ['zamboanga', 'Chavacano'],
  ['ceb', 'Cebuano/Bisaya'],
  ['cebuano', 'Cebuano/Bisaya'],
  ['bisaya', 'Cebuano/Bisaya'],
  ['cebuano/bisaya', 'Cebuano/Bisaya'],
  ['cebuano / bisaya', 'Cebuano/Bisaya'],
  ['hil', 'Hiligaynon'],
  ['hiligaynon', 'Hiligaynon'],
  ['ilonggo', 'Hiligaynon'],
  ['es', 'Spanish'],
  ['spanish', 'Spanish'],
])

export const CATEGORY_OPTIONS = ['Idioms', 'False Cognates', 'Honorifics', 'Expressions']

const CATEGORY_ALIAS_TO_CANONICAL = new Map([
  ['idiom', 'Idioms'],
  ['idioms', 'Idioms'],
  ['false cognate', 'False Cognates'],
  ['false cognates', 'False Cognates'],
  ['honorific', 'Honorifics'],
  ['honorifics', 'Honorifics'],
  ['expression', 'Expressions'],
  ['expressions', 'Expressions'],
  ['culture', 'Expressions'],
])

function normalizeText(value) {
  return String(value || '').trim().toLowerCase()
}

function splitTriggerWordCell(value) {
  return String(value || '')
    .split(/[|,]/)
    .map((entry) => entry.trim())
    .filter(Boolean)
}

export function toTriggerWordsArray(value) {
  const rawValues = Array.isArray(value) ? value : [value]
  const dedupe = new Set()
  const triggerWords = []

  for (const rawValue of rawValues) {
    for (const trigger of splitTriggerWordCell(rawValue)) {
      const normalized = normalizeText(trigger)
      if (!normalized || dedupe.has(normalized)) {
        continue
      }

      dedupe.add(normalized)
      triggerWords.push(trigger)
    }
  }

  return triggerWords
}

export function normalizeLanguageCode(languageValue) {
  const normalized = normalizeText(languageValue)
  if (!normalized) {
    return null
  }

  return LANGUAGE_ALIAS_TO_CANONICAL.get(normalized) || null
}

export function normalizeCategory(categoryValue) {
  const normalized = normalizeText(categoryValue)
  if (!normalized) {
    return null
  }

  return CATEGORY_ALIAS_TO_CANONICAL.get(normalized) || null
}

function mapWikiVozEntryToRecord(entry, index, source, timestamp) {
  if (!entry || typeof entry !== 'object') {
    return null
  }

  const term = String(entry.term || entry.title || '').trim()
  const definition = String(entry.definition || entry.description || '').trim()
  const language = normalizeLanguageCode(entry.language)
  const category = normalizeCategory(entry.category)
  const triggerWords = toTriggerWordsArray(entry.trigger_words || entry.triggerWords)

  if (!term || !definition || !language || !category || triggerWords.length === 0) {
    return null
  }

  const numericId = Number(entry.id)
  const id = Number.isInteger(numericId)
    ? numericId
    : String(entry.id || `${source}-${timestamp}-${index + 1}`)

  return {
    id,
    term,
    language,
    category,
    trigger_words: triggerWords,
    definition,
    image_url: String(entry.image_url || entry.imageUrl || '').trim(),
    updatedAt: entry.updated_at || new Date().toISOString(),
    source,
  }
}

export function mapWikiVozArrayToAdminRecords(entries, source = 'import') {
  if (!Array.isArray(entries)) {
    return []
  }

  const timestamp = Date.now()

  return entries
    .map((entry, index) => mapWikiVozEntryToRecord(entry, index, source, timestamp))
    .filter(Boolean)
}

function parseCsvLine(line) {
  const cells = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i]

    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"'
        i += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }

    if (char === ',' && !inQuotes) {
      cells.push(current.trim())
      current = ''
      continue
    }

    current += char
  }

  cells.push(current.trim())
  return cells
}

export function parseCsvTextToWikiVozArray(csvText) {
  const lines = String(csvText || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length < 2) {
    return []
  }

  const header = parseCsvLine(lines[0]).map((cell) => normalizeText(cell))

  const idIndex = header.indexOf('id')
  const triggerWordsIndex = header.indexOf('trigger_words')
  const languageIndex = header.indexOf('language')
  const categoryIndex = header.indexOf('category')
  const titleIndex = header.indexOf('title')
  const descriptionIndex = header.indexOf('description')
  const termIndex = header.indexOf('term')
  const definitionIndex = header.indexOf('definition')
  const imageUrlIndex = header.indexOf('image_url')

  if (
    triggerWordsIndex < 0
    || languageIndex < 0
    || categoryIndex < 0
    || (titleIndex < 0 && termIndex < 0)
    || (descriptionIndex < 0 && definitionIndex < 0)
  ) {
    return []
  }

  const rows = []

  for (let lineIndex = 1; lineIndex < lines.length; lineIndex += 1) {
    const columns = parseCsvLine(lines[lineIndex])

    rows.push({
      id: idIndex >= 0 ? columns[idIndex] : '',
      trigger_words: toTriggerWordsArray(columns[triggerWordsIndex] || ''),
      language: columns[languageIndex] || '',
      category: columns[categoryIndex] || '',
      title: (titleIndex >= 0 ? columns[titleIndex] : columns[termIndex]) || '',
      description: (descriptionIndex >= 0 ? columns[descriptionIndex] : columns[definitionIndex]) || '',
      image_url: imageUrlIndex >= 0 ? columns[imageUrlIndex] : '',
    })
  }

  return rows
}

export function parseJsonTextToWikiVozArray(jsonText) {
  const payload = JSON.parse(jsonText)

  if (Array.isArray(payload)) {
    return payload
  }

  if (Array.isArray(payload?.wiki_voz_entries)) {
    return payload.wiki_voz_entries
  }

  if (Array.isArray(payload?.results)) {
    return payload.results
  }

  return []
}
