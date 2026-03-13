/**
 * Header.jsx — Responsive header with Vinta icon and navigation
 * Mobile: Only logo/title shown, nav in bottom bar
 * Desktop: Logo + navigation items in top right
 */

import VintaIcon from '../icons/VintaIcon'
import { TranslateIcon, WikiVozIcon, SettingsIcon } from '../icons/NavIcons'

const NAV_ITEMS = [
  { id: 'translate', label: 'Translate', icon: TranslateIcon },
  { id: 'wiki-voz', label: 'Wiki-Voz', icon: WikiVozIcon },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
]

export default function Header({ activeScreen, onNavigate }) {
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
        <nav className="hidden md:flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const IconComponent = item.icon
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all duration-200 ${
                  activeScreen === item.id
                    ? 'bg-accent-magenta/15 text-accent-magenta'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
                }`}
              >
                <IconComponent className="w-5 h-5" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
