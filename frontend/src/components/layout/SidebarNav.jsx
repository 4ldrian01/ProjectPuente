/**
 * SidebarNav.jsx — Aesthetic 2026 fluid navigation rail for PUENTE.
 *
 * Architectural notes:
 * - The rail uses a two-state width system on desktop: 18rem (expanded) and 6rem (collapsed).
 * - Width and content transitions share a premium cubic-bezier curve for coherent motion language.
 * - In collapsed mode, labels shrink to zero width and opacity while icon anchors stay centered.
 * - Tooltips are rendered outside the rail so wayfinding remains clear without re-expanding.
 * - On mobile, the rail behaves as an off-canvas drawer and ignores collapsed desktop width.
 */

import {
  BookOpenText,
  ClipboardList,
  Database,
  Settings2,
  X,
  BarChart3,
  Waypoints,
} from 'lucide-react'
import { TranslationStudioIcon } from '../icons/NavIcons'

const NAV_GROUPS = [
  {
    key: 'workbench',
    label: 'CORE',
    items: [
      {
        id: 'translate',
        title: 'Translation Studio',
        subtitle: 'Inference console',
        icon: TranslationStudioIcon,
      },
    ],
  },
  {
    key: 'knowledge',
    label: 'INTELLIGENCE',
    items: [
      {
        id: 'wiki-voz',
        title: 'Wiki-Voz Lexicon',
        subtitle: 'Cultural knowledge',
        icon: BookOpenText,
      },
      {
        id: 'activity-logs',
        title: 'Activity Logs',
        subtitle: 'Observer telemetry',
        icon: ClipboardList,
      },
      {
        id: 'evaluation',
        title: 'System Evaluation',
        subtitle: 'Metrics and QA',
        icon: BarChart3,
      },
    ],
  },
  {
    key: 'admin',
    label: 'OPS',
    items: [
      {
        id: 'db-admin',
        title: 'Database Admin',
        subtitle: 'CulturalTerm records',
        icon: Database,
      },
      {
        id: 'settings',
        title: 'Settings & Health',
        subtitle: 'Runtime controls',
        icon: Settings2,
      },
    ],
  },
]

export default function SidebarNav({
  activeScreen,
  onNavigate,
  isCollapsed,
  mobileOpen,
  onCloseMobile,
  isMobileViewport,
}) {
  // Desktop width morphs between `w-72` and `w-24`. Mobile is always roomy enough
  // for full labels because discoverability matters more than compactness on small screens.
  const sidebarWidthClass = isCollapsed ? 'md:w-24 w-72' : 'md:w-72 w-72'

  // Off-canvas behavior on mobile; pinned and always visible from `md` and up.
  const mobileVisibilityClass = mobileOpen
    ? 'translate-x-0'
    : '-translate-x-full md:translate-x-0'
  const isHiddenOnMobile = isMobileViewport && !mobileOpen
  const buttonTabIndex = isHiddenOnMobile ? -1 : 0

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-50 ${sidebarWidthClass} ${mobileVisibilityClass} ${isHiddenOnMobile ? 'pointer-events-none' : ''} transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)]`}
      aria-label="Primary navigation"
      aria-hidden={isHiddenOnMobile}
      inert={isHiddenOnMobile ? '' : undefined}
    >
      <div className="relative flex h-full flex-col rounded-r-[1.25rem] border border-border-subtle/40 bg-bg-card/80 shadow-[var(--a26-shell-shadow)] backdrop-blur-xl md:rounded-tr-none">
        <div className="relative border-b border-border-subtle/40 px-3 py-4">
          <div className={`flex items-start justify-between gap-2 ${isCollapsed ? 'md:justify-center' : ''}`}>
            <div
              className={`flex min-w-0 items-center rounded-2xl border border-border-subtle/40 bg-bg-elevated/55 px-3 py-2.5 transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
                isCollapsed ? 'justify-center' : ''
              }`}
            >
              <Waypoints className="h-5 w-5 flex-shrink-0 text-accent-magenta" />
              <span
                className={`overflow-hidden whitespace-nowrap text-sm font-semibold tracking-[0.08em] text-text-primary transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
                  isCollapsed ? 'ml-0 max-w-0 opacity-0' : 'ml-2.5 max-w-[7rem] opacity-100'
                }`}
              >
                PUENTE
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onCloseMobile}
                className="inline-flex h-9 w-9 items-center justify-center rounded-2xl border border-border-subtle/40 bg-bg-card/70 text-text-secondary transition-all duration-300 hover:bg-bg-elevated hover:text-text-primary active:scale-95 md:hidden"
                aria-label="Close navigation menu"
                tabIndex={buttonTabIndex}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-5 overflow-x-visible overflow-y-auto px-2.5 py-4">
          {NAV_GROUPS.map((group, groupIndex) => (
            <section key={group.key} className="space-y-2">
              {isCollapsed && groupIndex > 0 ? (
                <div
                  className="mx-1 mb-2 h-px rounded-full bg-border-subtle/55"
                  aria-hidden="true"
                />
              ) : null}

              <p
                className={`overflow-hidden px-2 text-[10px] font-semibold uppercase tracking-widest text-text-secondary/75 transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
                  isCollapsed
                    ? 'max-h-0 -translate-y-1 opacity-0'
                    : 'max-h-4 translate-y-0 opacity-100'
                }`}
              >
                {group.label}
              </p>

              {group.items.map((item) => {
                const Icon = item.icon
                const isActive = activeScreen === item.id
                const iconSizeClass = item.id === 'translate' ? 'h-5 w-5' : 'h-4 w-4'

                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onNavigate(item.id)}
                    className={`group spring-nav-transition relative w-full rounded-2xl border transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] active:scale-95 ${
                      isCollapsed ? 'flex justify-center p-3' : 'px-3 py-3 text-left'
                    } ${
                      isActive
                        ? 'border-accent-magenta/35 bg-accent-magenta/12 text-text-primary shadow-[0_8px_30px_rgba(217,70,239,0.12)]'
                        : 'border-border-subtle/40 text-text-secondary hover:bg-bg-elevated/80 hover:text-text-primary'
                    }`}
                    aria-current={isActive ? 'page' : undefined}
                    aria-label={item.title}
                    tabIndex={buttonTabIndex}
                    title={item.title}
                  >
                    {/* Icon anchor never collapses, so scanability remains stable at 5rem width. */}
                    <div className={`flex w-full items-center ${isCollapsed ? 'justify-center' : ''}`}>
                      <span
                        className={`spring-icon-transition flex items-center justify-center rounded-xl p-3 transition-all duration-300 ${
                          isActive
                            ? 'scale-[1.04] bg-accent-magenta/18 text-accent-magenta'
                            : 'bg-bg-elevated/80 text-text-secondary group-hover:bg-bg-elevated group-hover:text-text-primary'
                        }`}
                      >
                        <Icon className={iconSizeClass} />
                      </span>

                      {/* Label column fades and shrinks to `w-0` in collapsed mode. */}
                      <span
                        className={`min-w-0 overflow-hidden whitespace-nowrap transition-all duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
                          isCollapsed ? 'ml-0 max-w-0 opacity-0' : 'ml-3 max-w-[15rem] opacity-100'
                        }`}
                      >
                        <span className="block truncate text-sm font-semibold leading-tight">
                          {item.title}
                        </span>
                        <span className="mt-1 block">
                          <span className="block truncate text-xs text-text-secondary/95">
                            {item.subtitle}
                          </span>
                        </span>
                      </span>
                    </div>

                    {/* Floating tooltip for collapsed desktop rail. */}
                    {isCollapsed ? (
                      <span className="pointer-events-none absolute left-[calc(100%+0.8rem)] top-1/2 hidden -translate-y-1/2 translate-x-1 whitespace-nowrap rounded-xl border border-border-subtle/40 bg-bg-card/95 px-2.5 py-1.5 text-xs font-medium text-text-primary opacity-0 shadow-[var(--a26-shell-shadow-soft)] backdrop-blur-xl transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100 md:inline-flex">
                        {item.title}
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </section>
          ))}
        </nav>

      </div>
    </aside>
  )
}
