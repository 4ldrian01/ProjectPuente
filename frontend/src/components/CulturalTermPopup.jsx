/**
 * CulturalTermPopup.jsx — Popup card for cultural term details
 * Appears when clicking yellow-underlined terms in translations
 */

import { useEffect, useMemo, useState } from 'react'
import { CloseIcon, SpeakerIcon } from './icons/NavIcons'
import { speakWithEdgeTts } from '../lib/ttsClient'

const LOCAL_PLACEHOLDER_SRC = '/local-assets/placeholder.jpg'

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

  const imageSrc = entry?.imageUrl || entry?.image_url || LOCAL_PLACEHOLDER_SRC
  const imageAlt = entry?.imageAlt || entry?.term || 'Wiki-Voz image'
  const sourceUrl = (entry?.sourceUrl || entry?.source_url || '').trim()

  const languageCode = useMemo(() => {
    const normalized = (entry?.language || '').trim().toLowerCase()
    return LANGUAGE_CODE_MAP[normalized] || 'en'
  }, [entry?.language])

  const canUseTts = backendUp && ttsAvailable

  useEffect(() => {
    const handleEsc = (event) => {
      if (event.key === 'Escape') onClose?.()
    }

    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [onClose])

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
        className="fixed inset-0 z-50 bg-overlay-scrim/65 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Centered modal */}
      <div className="fixed inset-0 z-[60] flex items-end justify-center p-3 sm:p-4 md:items-center">
        <div
          className="screen-transition-in w-full max-w-3xl max-h-[92vh] overflow-hidden rounded-2xl border border-accent-gold/35 bg-bg-card shadow-2xl shadow-overlay-scrim/35"
          role="dialog"
          aria-modal="true"
          aria-label={`${entry.term} details`}
        >
          <div className="flex items-center justify-between border-b border-border-subtle/60 px-4 py-3 sm:px-5">
            <div className="flex items-center gap-2.5">
              <span className="text-lg text-accent-gold">📖</span>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-accent-gold">Wiki-Voz</p>
                <p className="text-sm text-text-secondary">Cultural entry details</p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-1 text-text-secondary hover:text-text-primary transition-colors rounded-lg hover:bg-bg-elevated"
              aria-label="Close popup"
            >
              <CloseIcon className="w-5 h-5" />
            </button>
          </div>

          <div className="max-h-[calc(92vh-64px)] overflow-y-auto">
            <div className="grid gap-0 md:grid-cols-[1.1fr_1fr]">
              <div className="bg-bg-elevated/60">
                <div className="aspect-[16/10] w-full overflow-hidden md:h-full md:aspect-auto">
                  <img
                    src={imageSrc}
                    alt={imageAlt}
                    className="h-full w-full object-cover"
                    onError={(event) => {
                      event.currentTarget.src = LOCAL_PLACEHOLDER_SRC
                    }}
                  />
                </div>
              </div>

              <div className="p-4 sm:p-5">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <h4 className="text-xl font-bold text-text-primary">{entry.term}</h4>
                  {entry.language && (
                    <span className="rounded-full bg-accent-magenta/20 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-accent-magenta">
                      {entry.language}
                    </span>
                  )}
                  {entry.category && (
                    <span className="rounded-full bg-accent-gold/15 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-accent-gold">
                      {entry.category}
                    </span>
                  )}
                </div>

                <p className="text-sm leading-relaxed text-text-secondary sm:text-[15px]">
                  {entry.definition}
                </p>

                {sourceUrl && (
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-4 inline-block text-xs font-medium text-accent-magenta hover:underline"
                  >
                    View source reference
                  </a>
                )}

                <div className="mt-4 border-t border-border-subtle/60 pt-3">
                  <button
                    onClick={handleSpeak}
                    disabled={!canUseTts}
                    title={canUseTts ? 'Listen with Edge TTS' : 'Backend Edge TTS is unavailable'}
                    className="spring-nav-transition inline-flex items-center gap-1.5 rounded-lg border border-border-subtle px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-accent-gold/50 hover:text-accent-gold disabled:opacity-30"
                  >
                    <SpeakerIcon className={`spring-icon-transition w-4 h-4 ${ttsLoading ? 'animate-pulse' : ''}`} />
                    <span>Listen</span>
                  </button>
                </div>

                {ttsError && (
                  <div className="mt-3 rounded-lg border border-status-warning-border/80 bg-status-warning-bg/95 px-3 py-2 text-xs text-status-warning-text">
                    {ttsError}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
