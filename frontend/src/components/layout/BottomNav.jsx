/**
 * BottomNav.jsx — Fixed bottom navigation for mobile screens
 * Shows Translate, Wiki-Voz, Settings in that exact order
 */

import { TranslateIcon, WikiVozIcon, SettingsIcon } from '../icons/NavIcons'

const NAV_ITEMS = [
  { id: 'translate', label: 'Translate', icon: TranslateIcon },
  { id: 'wiki-voz', label: 'Wiki-Voz', icon: WikiVozIcon },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
]

export default function BottomNav({ activeScreen, onNavigate }) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-bg-card border-t border-border-subtle safe-area-bottom">
      <div className="flex items-stretch justify-around h-16">
        {NAV_ITEMS.map((item) => {
          const IconComponent = item.icon
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex-1 flex flex-col items-center justify-center gap-1 transition-all duration-200 ${
                activeScreen === item.id
                  ? 'text-accent-magenta'
                  : 'text-text-secondary'
              }`}
            >
              <IconComponent className="w-6 h-6" />
              <span className="text-xs font-medium">{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
