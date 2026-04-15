/**
 * GlobalHeader.jsx — Aesthetic 2026 command header.
 *
 * Architectural notes:
 * - Uses translucent layers + blur for depth without introducing heavy chroma noise.
 * - Exposes both mobile drawer control and desktop collapse control for unified nav behavior.
 * - Status chips progressively collapse at smaller breakpoints to prevent horizontal collisions.
 */

import {
  Activity,
  CloudOff,
  Gauge,
  Menu,
  PanelLeft,
  PanelLeftClose,
  RadioTower,
  RefreshCw,
} from 'lucide-react'

const SCREEN_TITLES = {
  translate: 'Translation Studio',
  'wiki-voz': 'Wiki-Voz Lexicon',
  'activity-logs': 'Activity Logs',
  evaluation: 'System Evaluation',
  'db-admin': 'Database Admin',
  settings: 'Settings & Health',
}

function formatLatency(latencyMs) {
  if (!Number.isFinite(latencyMs) || latencyMs < 0) {
    return '--'
  }

  return `${Math.round(latencyMs)} ms`
}

export default function GlobalHeader({
  activeScreen,
  pwaOnline,
  backendUp,
  latencyMs,
  checking,
  onPing,
  isSidebarCollapsed,
  onToggleSidebarCollapse,
  onToggleMobileNav,
  mobileNavOpen,
}) {
  const screenTitle = SCREEN_TITLES[activeScreen] || 'Operations View'

  return (
    <header className="sticky top-0 z-30 border-b border-border-subtle/60 bg-bg-card/80 shadow-[var(--a26-shell-shadow-soft)] backdrop-blur-xl">
      <div className="flex h-[4.5rem] items-center justify-between gap-3 px-3 py-3 sm:px-4 lg:px-6">
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
          <button
            type="button"
            onClick={onToggleMobileNav}
            className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-border-subtle/70 bg-bg-card/70 text-text-secondary transition-all duration-300 hover:bg-bg-elevated hover:text-text-primary active:scale-[0.98] md:hidden"
            aria-label={mobileNavOpen ? 'Close navigation menu' : 'Open navigation menu'}
          >
            <Menu className="h-[1.125rem] w-[1.125rem]" />
          </button>

          <button
            type="button"
            onClick={onToggleSidebarCollapse}
            className="hidden h-10 w-10 items-center justify-center rounded-2xl border border-border-subtle/70 bg-bg-card/70 text-text-secondary transition-all duration-300 hover:bg-bg-elevated hover:text-text-primary active:scale-[0.98] md:inline-flex"
            aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isSidebarCollapsed ? <PanelLeft className="h-[1.125rem] w-[1.125rem]" /> : <PanelLeftClose className="h-[1.125rem] w-[1.125rem]" />}
          </button>

          <h1 className="sr-only">{screenTitle}</h1>
        </div>

        <div className="flex items-center gap-2">
          <div
            className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold sm:inline-flex ${
              pwaOnline
                ? 'border-status-success-border/70 bg-status-success-bg/60 text-status-success-text'
                : 'border-status-danger-border/70 bg-status-danger-bg/60 text-status-danger-text'
            }`}
            title={pwaOnline ? 'PWA online' : 'PWA offline'}
          >
            {pwaOnline ? <RadioTower className="h-3.5 w-3.5" /> : <CloudOff className="h-3.5 w-3.5" />}
            {pwaOnline ? 'PWA Online' : 'PWA Offline'}
          </div>

          <div
            className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold lg:inline-flex ${
              backendUp
                ? 'border-status-info-border/70 bg-status-info-bg/70 text-status-info-text'
                : 'border-status-warning-border/70 bg-status-warning-bg/70 text-status-warning-text'
            }`}
            title="Backend health latency ping"
          >
            <Gauge className="h-3.5 w-3.5" />
            {backendUp ? `Latency ${formatLatency(latencyMs)}` : 'Backend Down'}
          </div>

          <button
            type="button"
            onClick={onPing}
            className="spring-nav-transition inline-flex items-center gap-2 rounded-full border border-border-subtle/70 bg-bg-card/80 px-3 py-1.5 text-xs font-semibold text-text-secondary transition-all duration-300 hover:border-accent-magenta/35 hover:bg-bg-elevated hover:text-text-primary active:scale-[0.98]"
            title="Refresh backend health check"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${checking ? 'animate-spin' : ''}`} />
            Ping
          </button>

          <span className="hidden items-center gap-2 rounded-full border border-border-subtle/70 bg-bg-card/80 px-3 py-1.5 text-xs font-semibold text-text-secondary xl:inline-flex">
            <Activity className="h-3.5 w-3.5" />
            Observer Loop Active
          </span>
        </div>
      </div>
    </header>
  )
}
