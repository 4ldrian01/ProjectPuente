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
  { code: 'ceb',  label: 'Cebuano/Bisaya' },
  { code: 'hil',  label: 'Hiligaynon' },
  { code: 'es',   label: 'Spanish' },
]

const getLang = (code) => ALL_LANGUAGES.find((l) => l.code === code)

export default function LanguageSelector({
  selected,
  onSelect,
  visibleCodes,
  dropdownCodes,
  excludeCode,
  tone = 'primary',
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
  const hasOverflowLanguages = dropdown.length > 0

  const selectedLabel = getLang(selected)?.label ?? 'Select'
  const activeTabKey = selectedInDropdown ? '__dropdown__' : selected
  const isSubtleTone = tone === 'subtle'
  const activeTextClass = isSubtleTone ? 'text-text-primary' : 'text-accent-magenta'
  const idleTextClass = isSubtleTone
    ? 'text-text-secondary/85 hover:text-text-primary'
    : 'text-text-secondary hover:text-text-primary'
  const activeRowClass = isSubtleTone ? 'text-text-primary font-medium' : 'text-accent-magenta font-medium'
  const indicatorColorClass = isSubtleTone ? 'bg-text-secondary/65' : 'bg-accent-magenta'
  const borderToneClass = isSubtleTone ? 'border-border-subtle/22' : 'border-border-subtle/35'
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
          type="button"
          onClick={() => setOpen(!open)}
          className="spring-nav-transition flex items-center gap-2 px-1 py-2 text-sm font-medium text-text-primary bg-transparent active:scale-[0.98]"
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span>{selectedLabel}</span>
          <ChevronDownIcon
            className={`w-4 h-4 text-text-secondary transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </button>

        {open && (
          <div className="animate-fade-in absolute top-full left-0 z-40 mt-1 min-w-[11.25rem] rounded-lg border border-border-subtle bg-bg-card/95 py-1 shadow-xl backdrop-blur-sm" role="listbox">
            {allAvailable.map((lang) => (
              <button
                type="button"
                key={lang.code}
                onClick={() => { onSelect(lang.code); setOpen(false) }}
                className={`spring-nav-transition w-full px-4 py-2.5 text-left text-sm ${
                  selected === lang.code
                    ? activeRowClass
                    : 'text-text-primary hover:bg-bg-elevated/50 hover:pl-5'
                }`}
                role="option"
                aria-selected={selected === lang.code}
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
        className={`hidden md:flex items-center gap-0.5 border-b relative ${borderToneClass}`}
      >
        {visible.map((lang, index) => {
          const isLastVisible = index === visible.length - 1
          const fadeForContinuation = isLastVisible && hasOverflowLanguages

          return (
            <button
              type="button"
              key={lang.code}
              onClick={() => onSelect(lang.code)}
              data-tab-key={lang.code}
              className={`spring-nav-transition px-3 py-2 text-sm font-medium whitespace-nowrap relative will-change-transform ${
                fadeForContinuation ? 'pr-4' : ''
              } ${
                selected === lang.code
                  ? `${activeTextClass} -translate-y-px`
                  : `${idleTextClass} hover:-translate-y-px`
              }`}
            >
              <span>
                {lang.label}
              </span>

              {fadeForContinuation && (
                <span
                  className="pointer-events-none absolute inset-y-0 right-0 w-1/2 rounded-r-md bg-gradient-to-r from-transparent via-bg-card/70 to-bg-card/95"
                  aria-hidden="true"
                />
              )}
            </button>
          )
        })}

        {/* Dropdown chevron for overflow languages */}
        {dropdown.length > 0 && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setOpen(!open)}
              data-tab-key="__dropdown__"
              className={`spring-nav-transition px-3 py-2 text-sm font-medium whitespace-nowrap flex items-center gap-1 relative will-change-transform ${
                selectedInDropdown
                  ? `${activeTextClass} -translate-y-px`
                  : `${idleTextClass} hover:-translate-y-px`
              }`}
              aria-haspopup="listbox"
              aria-expanded={open}
            >
              {selectedInDropdown && <span>{getLang(selected)?.label}</span>}
              <ChevronDownIcon
                className={`h-[0.875rem] w-[0.875rem] transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
              />
            </button>

            {open && (
              <div className="animate-fade-in absolute top-full left-0 z-40 mt-1 min-w-[10rem] rounded-lg border border-border-subtle bg-bg-card/95 py-1 shadow-xl backdrop-blur-sm" role="listbox">
                {dropdown.map((lang) => (
                  <button
                    type="button"
                    key={lang.code}
                    onClick={() => { onSelect(lang.code); setOpen(false) }}
                    className={`spring-nav-transition w-full px-4 py-2.5 text-left text-sm ${
                      selected === lang.code
                        ? activeRowClass
                        : 'text-text-primary hover:bg-bg-elevated/50 hover:pl-5'
                    }`}
                    role="option"
                    aria-selected={selected === lang.code}
                  >
                    {lang.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <span
          className={`spring-indicator-transition pointer-events-none absolute bottom-0 h-0.5 rounded-full ${indicatorColorClass} ${
            indicator.visible ? 'opacity-100' : 'opacity-0'
          }`}
          style={{ left: `${indicator.left}px`, width: `${indicator.width}px` }}
          aria-hidden="true"
        />
      </div>
    </div>
  )
}
