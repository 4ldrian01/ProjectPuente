/**
 * Header.jsx — Responsive header with Vinta icon and navigation
 * Mobile: Only logo/title shown, nav in bottom bar
 * Desktop: Logo + navigation items in top right
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import VintaIcon from '../icons/VintaIcon'
import { TranslateIcon, WikiVozIcon, SettingsIcon } from '../icons/NavIcons'

const NAV_ITEMS = [
  { id: 'translate', label: 'Translate', icon: TranslateIcon },
  { id: 'wiki-voz', label: 'Wiki-Voz', icon: WikiVozIcon },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
]

export default function Header({ activeScreen, onNavigate }) {
  const navRef = useRef(null)
  const [indicator, setIndicator] = useState({ left: 0, width: 0, visible: false })

  const layoutSignature = useMemo(
    () => `${activeScreen}|${NAV_ITEMS.map((item) => item.id).join(',')}`,
    [activeScreen],
  )

  const updateIndicator = useCallback(() => {
    const nav = navRef.current
    if (!nav) return

    const activeButton = nav.querySelector(`[data-nav-key="${activeScreen}"]`)
    if (!activeButton) {
      setIndicator((prev) => ({ ...prev, visible: false }))
      return
    }

    const navRect = nav.getBoundingClientRect()
    const activeRect = activeButton.getBoundingClientRect()

    setIndicator({
      left: activeRect.left - navRect.left,
      width: activeRect.width,
      visible: true,
    })
  }, [activeScreen])

  useEffect(() => {
    const raf = requestAnimationFrame(updateIndicator)
    window.addEventListener('resize', updateIndicator)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', updateIndicator)
    }
  }, [layoutSignature, updateIndicator])

  return (
    <header className="sticky top-0 z-50 border-b border-border-subtle bg-bg-dark/95 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Logo Section */}
        <div className="flex items-center gap-3">
          <VintaIcon className="w-10 h-10" />
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary">
            PUENTE
          </h1>
        </div>

        {/* Desktop Navigation - Hidden on mobile */}
        <nav
          ref={navRef}
          className="hidden md:flex items-center gap-1 relative rounded-xl border border-border-subtle/70 bg-bg-card/70 p-1"
        >
          {NAV_ITEMS.map((item) => {
            const IconComponent = item.icon
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                data-nav-key={item.id}
                className={`group spring-nav-transition relative z-10 flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm will-change-transform ${
                  activeScreen === item.id
                    ? 'text-accent-magenta scale-[1.01]'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated/60 hover:-translate-y-[1px]'
                }`}
              >
                <IconComponent className={`spring-icon-transition w-5 h-5 ${activeScreen === item.id ? 'scale-105' : 'group-hover:scale-105'}`} />
                <span>{item.label}</span>
              </button>
            )
          })}

          <span
            className={`spring-indicator-transition pointer-events-none absolute inset-y-1 rounded-lg border border-accent-magenta/35 bg-accent-magenta/12 shadow-[0_0_20px_rgba(217,70,239,0.14)] ${
              indicator.visible ? 'opacity-100' : 'opacity-0'
            }`}
            style={{
              left: `${indicator.left}px`,
              width: `${indicator.width}px`,
            }}
            aria-hidden="true"
          />

          <span
            className={`spring-indicator-transition pointer-events-none absolute -bottom-px h-0.5 rounded-full bg-accent-magenta ${
              indicator.visible ? 'opacity-100' : 'opacity-0'
            }`}
            style={{
              left: `${indicator.left + 10}px`,
              width: `${Math.max(0, indicator.width - 20)}px`,
            }}
            aria-hidden="true"
          />
        </nav>
      </div>
    </header>
  )
}
