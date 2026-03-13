/**
 * CulturalTermPopup.jsx — Popup card for cultural term details
 * Appears when clicking yellow-underlined terms in translations
 */

import { useMemo, useState } from 'react'
import { CloseIcon, SpeakerIcon } from './icons/NavIcons'
import { speakWithEdgeTts } from '../lib/ttsClient'

const LANGUAGE_CODE_MAP = {
  chavacano: 'cbk',
  zamboanga: 'cbk',
  hiligaynon: 'hil',
  ilonggo: 'hil',
  cebuano: 'ceb',
  'cebuano/bisaya': 'ceb',
  bisaya: 'ceb',
  tagalog: 'tl',
  english: 'en',
}

export default function CulturalTermPopup({ entry, onClose, apiUrl, backendUp, ttsAvailable }) {
  const [ttsError, setTtsError] = useState('')
  const [ttsLoading, setTtsLoading] = useState(false)

  const languageCode = useMemo(() => {
    const normalized = (entry?.language || '').trim().toLowerCase()
    return LANGUAGE_CODE_MAP[normalized] || 'en'
  }, [entry?.language])

  const canUseTts = backendUp && ttsAvailable

  if (!entry) return null

  const handleSpeak = async () => {
    if (!canUseTts) return

    setTtsError('')
    setTtsLoading(true)

    try {
      await speakWithEdgeTts({
        apiUrl,
        text: `${entry.term}. ${entry.definition}`,
        langCode: languageCode,
      })
    } catch (err) {
      if (err?.code !== 'ERR_CANCELED') {
        setTtsError(err.message || 'Text-to-speech failed.')
      }
    } finally {
      setTtsLoading(false)
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40 md:bg-transparent"
        onClick={onClose}
      />
      
      {/* Popup Card */}
      <div 
        className={`
          fixed md:absolute z-50 
          left-4 right-4 md:left-0 md:right-auto
          bottom-20 md:bottom-auto md:top-full md:mt-2
          md:w-80 lg:w-96
          animate-slide-up
        `}
      >
        <div className="bg-bg-card border border-accent-gold/40 rounded-xl p-4 shadow-2xl shadow-accent-gold/10">
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-accent-gold text-lg">📖</span>
              <span className="text-accent-gold font-semibold text-xs uppercase tracking-wider">
                Wiki-Voz
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1 text-text-secondary hover:text-text-primary transition-colors rounded-lg hover:bg-bg-elevated"
              aria-label="Close popup"
            >
              <CloseIcon className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="flex gap-4">
            {/* Image */}
            {entry.imageUrl && (
              <div className="shrink-0">
                <img
                  src={entry.imageUrl}
                  alt={entry.term}
                  className="w-20 h-20 md:w-24 md:h-24 rounded-lg object-cover border border-border-subtle"
                  onError={(e) => {
                    e.target.style.display = 'none'
                  }}
                />
              </div>
            )}

            {/* Text Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="text-text-primary font-bold text-lg">
                  {entry.term}
                </h4>
                <span className="text-xs bg-accent-magenta/20 text-accent-magenta px-2 py-0.5 rounded-full">
                  {entry.language}
                </span>
              </div>
              <p className="text-text-secondary text-sm leading-relaxed line-clamp-4">
                {entry.definition}
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border-subtle">
            <button
              onClick={handleSpeak}
              disabled={!canUseTts}
              title={canUseTts ? 'Listen with Edge TTS' : 'Backend Edge TTS is unavailable'}
              className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-accent-gold transition-colors disabled:opacity-30"
            >
              <SpeakerIcon className={`w-4 h-4 ${ttsLoading ? 'animate-pulse' : ''}`} />
              <span>Listen</span>
            </button>
            <span className="text-border-subtle">•</span>
            <span className="text-xs text-text-secondary/70 capitalize">
              {entry.category}
            </span>
          </div>

          {ttsError && (
            <div className="mt-3 rounded-lg border border-amber-700/70 bg-amber-900/20 px-3 py-2 text-xs text-amber-200">
              {ttsError}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
