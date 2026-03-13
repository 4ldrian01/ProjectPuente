/**
 * LanguageSelector.jsx — Google Translate-inspired language selector.
 *
 * Desktop / Laptop:
 *   Tabbed buttons with bottom-border underline animation on hover & active.
 *   No rectangular background on hover. Overflow languages in a dropdown.
 *
 * Mobile / Tablet (<md):
 *   Single transparent dropdown menu consolidating all languages.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDownIcon } from './icons/NavIcons'

const ALL_LANGUAGES = [
  { code: 'auto', label: 'Detect Language' },
  { code: 'en',   label: 'English' },
  { code: 'tl',   label: 'Tagalog' },
  { code: 'cbk',  label: 'Chavacano' },
  { code: 'hil',  label: 'Hiligaynon' },
  { code: 'ceb',  label: 'Cebuano/Bisaya' },
]

const getLang = (code) => ALL_LANGUAGES.find((l) => l.code === code)

export default function LanguageSelector({
  selected,
  onSelect,
  visibleCodes,
  dropdownCodes,
  excludeCode,
}) {
  const [open, setOpen] = useState(false)
  const [indicator, setIndicator] = useState({ left: 0, width: 0, visible: false })
  const ref = useRef(null)
  const tabsTrackRef = useRef(null)

  /* close dropdown on outside click */
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  /* All available languages (excluding the "other side" selection) */
  const allAvailable = [...visibleCodes, ...dropdownCodes]
    .filter((c) => c !== excludeCode)
    .map(getLang)
    .filter(Boolean)

  const visible = visibleCodes
    .filter((c) => c !== excludeCode)
    .map(getLang)
    .filter(Boolean)

  const dropdown = dropdownCodes
    .filter((c) => c !== excludeCode)
    .map(getLang)
    .filter(Boolean)

  const selectedInDropdown =
    dropdownCodes.includes(selected) && selected !== excludeCode

  const selectedLabel = getLang(selected)?.label ?? 'Select'
  const activeTabKey = selectedInDropdown ? '__dropdown__' : selected
  const layoutSignature = useMemo(
    () => `${visibleCodes.join(',')}|${dropdownCodes.join(',')}|${excludeCode ?? ''}|${selectedLabel}`,
    [visibleCodes, dropdownCodes, excludeCode, selectedLabel],
  )

  const updateIndicator = useCallback(() => {
    const track = tabsTrackRef.current
    if (!track) return

    const activeButton = track.querySelector(`[data-tab-key="${activeTabKey}"]`)
    if (!activeButton) {
      setIndicator((prev) => ({ ...prev, visible: false }))
      return
    }

    const trackRect = track.getBoundingClientRect()
    const activeRect = activeButton.getBoundingClientRect()

    setIndicator({
      left: activeRect.left - trackRect.left,
      width: activeRect.width,
      visible: true,
    })
  }, [activeTabKey])

  useEffect(() => {
    const raf = requestAnimationFrame(updateIndicator)
    window.addEventListener('resize', updateIndicator)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', updateIndicator)
    }
  }, [updateIndicator, layoutSignature])

  return (
    <div ref={ref}>
      {/* ═══ MOBILE / TABLET — single transparent dropdown ═══ */}
      <div className="md:hidden relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-1 py-2 text-sm font-medium text-text-primary bg-transparent transition-colors"
        >
          <span>{selectedLabel}</span>
          <ChevronDownIcon
            className={`w-4 h-4 text-text-secondary transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1 rounded-lg shadow-xl z-40 min-w-45 border border-border-subtle bg-bg-dark/95 backdrop-blur-sm py-1">
            {allAvailable.map((lang) => (
              <button
                key={lang.code}
                onClick={() => { onSelect(lang.code); setOpen(false) }}
                className={`w-full px-4 py-2.5 text-left text-sm transition-colors ${
                  selected === lang.code
                    ? 'text-accent-magenta font-medium'
                    : 'text-text-primary hover:bg-bg-elevated/50'
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ═══ DESKTOP / LAPTOP — tabbed buttons with underline ═══ */}
      <div
        ref={tabsTrackRef}
        className="hidden md:flex items-center gap-0.5 border-b border-border-subtle/35 relative"
      >
        {visible.map((lang) => (
          <button
            key={lang.code}
            onClick={() => onSelect(lang.code)}
            data-tab-key={lang.code}
            className={`px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors relative ${
              selected === lang.code
                ? 'text-accent-magenta'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {lang.label}
          </button>
        ))}

        {/* Dropdown chevron for overflow languages */}
        {dropdown.length > 0 && (
          <div className="relative">
            <button
              onClick={() => setOpen(!open)}
              data-tab-key="__dropdown__"
              className={`px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors flex items-center gap-1 relative ${
                selectedInDropdown
                  ? 'text-accent-magenta'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              {selectedInDropdown && <span>{getLang(selected)?.label}</span>}
              <ChevronDownIcon
                className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
              />
            </button>

            {open && (
              <div className="absolute top-full left-0 mt-1 rounded-lg shadow-xl z-40 min-w-40 border border-border-subtle bg-bg-dark/95 backdrop-blur-sm py-1">
                {dropdown.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => { onSelect(lang.code); setOpen(false) }}
                    className={`w-full px-4 py-2.5 text-left text-sm transition-colors ${
                      selected === lang.code
                        ? 'text-accent-magenta font-medium'
                        : 'text-text-primary hover:bg-bg-elevated/50'
                    }`}
                  >
                    {lang.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <span
          className={`pointer-events-none absolute bottom-0 h-0.5 rounded-full bg-accent-magenta transition-all duration-300 ease-out ${
            indicator.visible ? 'opacity-100' : 'opacity-0'
          }`}
          style={{ left: `${indicator.left}px`, width: `${indicator.width}px` }}
          aria-hidden="true"
        />
      </div>
    </div>
  )
}
