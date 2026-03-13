/**
 * wikiVozData.js - Offline Wiki-Voz dataset for the frontend.
 *
 * Purpose:
 * - Provide a richer local fallback dataset when the backend Wiki-Voz API is
 *   unavailable.
 *
 * How it works:
 * - Mixes curated, display-ready cultural entries with explicit template slots
 *   that can be safely filled in later by curators.
 *
 * Why it matters:
 * - The app stays useful offline, the modal stays fully data-driven, and the
 *   project can grow without hardcoding modal content per term.
 */

const CURATOR_NOTE = 'Starter template for Wiki-Voz curators. Replace this text with a verified local definition, update the image URL, and attach a trusted source link.'

function createWikiEntry({
  id,
  term,
  language,
  definition,
  category,
  imageUrl = '',
  sourceUrl = '',
  imageAlt = '',
  highlightAliases = [],
  contentStatus = 'curated',
}) {
  return {
    id,
    term,
    language,
    definition,
    category,
    imageUrl,
    sourceUrl,
    imageAlt: imageAlt || `${term} image`,
    highlightAliases,
    contentStatus,
    templateReady: contentStatus === 'template',
  }
}

function createTemplateEntries(language, prefix, count, categories) {
  return Array.from({ length: count }, (_, index) => {
    const slot = String(index + 1).padStart(2, '0')
    const category = categories[index % categories.length]

    return createWikiEntry({
      id: `${prefix}-template-${slot}`,
      term: `Template - ${language} ${category} ${slot}`,
      language,
      category,
      definition: `${CURATOR_NOTE} Slot ${slot} reserved for a ${language.toLowerCase()} ${category} entry.`,
      imageAlt: `Replace with a real image for ${language} ${category} slot ${slot}`,
      contentStatus: 'template',
    })
  })
}

const curatedEntries = [
  // Chavacano / Zamboanga
  createWikiEntry({
    id: 'satti',
    term: 'Satti',
    language: 'Chavacano',
    definition: 'A Zamboanga dish of grilled meat skewers served with a spicy sauce and often paired with puso rice.',
    category: 'food',
    highlightAliases: ['satti'],
  }),
  createWikiEntry({
    id: 'vinta',
    term: 'Vinta',
    language: 'Chavacano',
    definition: 'A traditional outrigger boat recognized for its colorful sail and strong association with western Mindanao maritime culture.',
    category: 'culture',
    highlightAliases: ['vinta'],
  }),
  createWikiEntry({
    id: 'mascota',
    term: 'Mascota',
    language: 'Chavacano',
    definition: 'A Chavacano term used for a pet or companion animal, often carrying a warm household tone.',
    category: 'lifestyle',
    highlightAliases: ['mascota'],
  }),
  createWikiEntry({
    id: 'pangalay',
    term: 'Pangalay',
    language: 'Chavacano',
    definition: 'A traditional dance form known for controlled hand and arm movements and ceremonial performance contexts.',
    category: 'culture',
    highlightAliases: ['pangalay'],
  }),
  createWikiEntry({
    id: 'curacha',
    term: 'Curacha',
    language: 'Chavacano',
    definition: 'A crab delicacy commonly associated with Zamboanga cuisine and frequently served in rich savory sauces.',
    category: 'food',
    highlightAliases: ['curacha'],
  }),
  createWikiEntry({
    id: 'knickerbocker',
    term: 'Knickerbocker',
    language: 'Chavacano',
    definition: 'A colorful fruit-and-ice dessert drink popular in Zamboanga merienda culture.',
    category: 'food',
    highlightAliases: ['knickerbocker'],
  }),
  createWikiEntry({
    id: 'hermosa',
    term: 'Hermosa',
    language: 'Chavacano',
    definition: 'A Chavacano word meaning beautiful, often used in praise, greetings, and affectionate descriptions.',
    category: 'expression',
    highlightAliases: ['hermosa'],
  }),
  createWikiEntry({
    id: 'regatta',
    term: 'Regatta de Zamboanga',
    language: 'Chavacano',
    definition: 'A festival event known for vinta races and public celebration of Zamboanga sea culture.',
    category: 'festival',
    highlightAliases: ['regatta', 'regatta de zamboanga'],
  }),
  createWikiEntry({
    id: 'abuela',
    term: 'Abuela',
    language: 'Chavacano',
    definition: 'Grandmother in Chavacano, inherited from Spanish and commonly used as a family term of affection and respect.',
    category: 'family',
    highlightAliases: ['abuela'],
  }),
  createWikiEntry({
    id: 'paseo-del-mar',
    term: 'Paseo del Mar',
    language: 'Chavacano',
    definition: 'A waterfront public space in Zamboanga City commonly associated with evening walks, food stalls, and local gatherings.',
    category: 'place',
    highlightAliases: ['paseo del mar'],
  }),

  // Hiligaynon / Western Visayas
  createWikiEntry({
    id: 'dinagyang',
    term: 'Dinagyang',
    language: 'Hiligaynon',
    definition: 'A major Iloilo festival known for drum-driven street performance and devotion to the Santo Nino.',
    category: 'festival',
    highlightAliases: ['dinagyang'],
  }),
  createWikiEntry({
    id: 'batchoy',
    term: 'La Paz Batchoy',
    language: 'Hiligaynon',
    definition: 'A noodle soup strongly associated with Iloilo and often treated as a signature comfort food of the region.',
    category: 'food',
    highlightAliases: ['batchoy', 'la paz batchoy'],
  }),
  createWikiEntry({
    id: 'ilonggo',
    term: 'Ilonggo',
    language: 'Hiligaynon',
    definition: 'A label for people, identity, and culture closely associated with Iloilo and nearby Hiligaynon-speaking communities.',
    category: 'culture',
    highlightAliases: ['ilonggo'],
  }),
  createWikiEntry({
    id: 'hablon',
    term: 'Hablon',
    language: 'Hiligaynon',
    definition: 'A handwoven textile tradition associated with Panay craftsmanship and heritage fabric production.',
    category: 'craft',
    highlightAliases: ['hablon'],
  }),
  createWikiEntry({
    id: 'kbl',
    term: 'Kadyos Baboy Langka',
    language: 'Hiligaynon',
    definition: 'A savory Iloilo dish made with pigeon peas, pork, and jackfruit, commonly shortened to KBL.',
    category: 'food',
    highlightAliases: ['kbl', 'kadyos baboy langka'],
  }),
  createWikiEntry({
    id: 'kansi',
    term: 'Kansi',
    language: 'Hiligaynon',
    definition: 'A sour beef soup associated with Negros Occidental and neighboring Hiligaynon-speaking food culture.',
    category: 'food',
    highlightAliases: ['kansi'],
  }),

  // Cebuano / Bisaya
  createWikiEntry({
    id: 'puso',
    term: 'Puso',
    language: 'Cebuano/Bisaya',
    definition: 'Rice packed in woven coconut leaves, designed to be easy to carry and commonly paired with grilled food.',
    category: 'food',
    highlightAliases: ['puso'],
  }),
  createWikiEntry({
    id: 'sinulog',
    term: 'Sinulog',
    language: 'Cebuano/Bisaya',
    definition: 'A major Cebu festival recognized for dance processions, drum rhythms, and devotion to the Santo Nino.',
    category: 'festival',
    highlightAliases: ['sinulog'],
  }),
  createWikiEntry({
    id: 'lechon-cebu',
    term: 'Lechon Cebu',
    language: 'Cebuano/Bisaya',
    definition: 'Roasted pig strongly associated with Cebu culinary identity and often noted for its seasoned meat and crisp skin.',
    category: 'food',
    highlightAliases: ['lechon cebu', 'lechon'],
  }),
  createWikiEntry({
    id: 'otap',
    term: 'Otap',
    language: 'Cebuano/Bisaya',
    definition: 'A crisp, layered sugar pastry widely associated with Cebu pasalubong culture.',
    category: 'food',
    highlightAliases: ['otap'],
  }),
  createWikiEntry({
    id: 'sutukil',
    term: 'Sutukil',
    language: 'Cebuano/Bisaya',
    definition: 'A seafood dining style whose name comes from sugba, tuwa, and kilaw cooking methods.',
    category: 'food',
    highlightAliases: ['sutukil'],
  }),
  createWikiEntry({
    id: 'larsian',
    term: 'Larsian',
    language: 'Cebuano/Bisaya',
    definition: 'A well-known open-air grilled food area associated with casual night eating in Cebu City.',
    category: 'place',
    highlightAliases: ['larsian'],
  }),
]

const chavacanoTemplates = createTemplateEntries('Chavacano', 'cbk', 24, [
  'food', 'festival', 'place', 'expression', 'craft', 'family', 'music', 'heritage',
])

const hiligaynonTemplates = createTemplateEntries('Hiligaynon', 'hil', 26, [
  'food', 'festival', 'craft', 'place', 'expression', 'heritage', 'family', 'tradition',
])

const cebuanoTemplates = createTemplateEntries('Cebuano/Bisaya', 'ceb', 28, [
  'food', 'festival', 'craft', 'place', 'expression', 'heritage', 'transport', 'family', 'market',
])

const templateEntryCount =
  chavacanoTemplates.length +
  hiligaynonTemplates.length +
  cebuanoTemplates.length

export const WIKI_VOZ_ENTRIES = [
  ...curatedEntries,
  ...chavacanoTemplates,
  ...hiligaynonTemplates,
  ...cebuanoTemplates,
]

export const WIKI_VOZ_ENTRY_GOAL = {
  currentSeedTotal: WIKI_VOZ_ENTRIES.length,
  verifiedCuratedEntries: curatedEntries.length,
  templateEntries: templateEntryCount,
  futureTargetPerLanguage: 100,
  futureTargetTotal: 300,
}

export const CULTURAL_TERMS_MAP = WIKI_VOZ_ENTRIES
  .filter((entry) => entry.contentStatus !== 'template')
  .reduce((acc, entry) => {
    const aliases = [entry.term, ...(entry.highlightAliases || [])]

    aliases.forEach((alias) => {
      const normalized = alias.toLowerCase().trim()
      if (normalized) acc[normalized] = entry.id
    })

    return acc
  }, {})

export function getCulturalEntry(termId) {
  return WIKI_VOZ_ENTRIES.find((entry) => entry.id === termId) || null
}
