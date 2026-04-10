/**
 * BottomNav.jsx — Fixed bottom navigation for mobile screens
 * Shows Translate, Wiki-Voz, Settings in that exact order
 */

import { TranslateIcon, WikiVozIcon, SettingsIcon } from '../icons/NavIcons'
import { Activity } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'translate', label: 'Translate', icon: TranslateIcon },
  { id: 'wiki-voz', label: 'Wiki-Voz', icon: WikiVozIcon },
  { id: 'evaluation', label: 'Evaluate', icon: Activity },
  { id: 'settings', label: 'Settings', icon: SettingsIcon },
]

export default function BottomNav({ activeScreen, onNavigate }) {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 border-t border-border-subtle bg-bg-card/95 backdrop-blur-md safe-area-bottom">
      <div className="flex h-16 items-stretch justify-around px-1.5">
        {NAV_ITEMS.map((item) => {
          const IconComponent = item.icon
          const isActive = activeScreen === item.id

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`spring-nav-transition relative flex flex-1 flex-col items-center justify-center gap-1 px-1 will-change-transform ${
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
              <span className={`spring-icon-transition whitespace-nowrap text-[11px] font-medium leading-none ${isActive ? 'scale-[1.02]' : ''}`}>{item.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
