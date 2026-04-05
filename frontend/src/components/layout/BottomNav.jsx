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
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-border-subtle bg-bg-card/95 backdrop-blur-md safe-area-bottom">
      <div className="flex items-stretch justify-around h-16">
        {NAV_ITEMS.map((item) => {
          const IconComponent = item.icon
          const isActive = activeScreen === item.id

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`spring-nav-transition relative flex-1 flex flex-col items-center justify-center gap-1 will-change-transform ${
                isActive
                  ? 'text-accent-magenta -translate-y-[1px]'
                  : 'text-text-secondary hover:text-text-primary active:scale-[0.98]'
              }`}
            >
              <span
                className={`spring-indicator-transition absolute top-1.5 h-0.5 w-8 rounded-full bg-accent-magenta ${
                  isActive ? 'opacity-100 scale-100' : 'opacity-0 scale-75'
                }`}
                aria-hidden="true"
              />

              <IconComponent className={`spring-icon-transition w-6 h-6 ${isActive ? 'scale-[1.08]' : ''}`} />
              <span className={`spring-icon-transition text-xs font-medium ${isActive ? 'scale-[1.02]' : ''}`}>{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
