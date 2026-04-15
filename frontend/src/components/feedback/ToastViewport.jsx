/**
 * ToastViewport.jsx — Notification stack renderer.
 * Summary: Presents transient success/warning/error/info messages with accessible live-region semantics.
 */

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'

const TOAST_VARIANTS = {
  info: {
    icon: Info,
    container: 'border-status-info-border/70 bg-status-info-bg/92 text-status-info-text',
    iconWrap: 'border-status-info-border/70 bg-status-info-bg/65 text-status-info-text',
    progress: 'bg-status-info-border/90',
  },
  success: {
    icon: CheckCircle2,
    container: 'border-status-success-border/70 bg-status-success-bg/92 text-status-success-text',
    iconWrap: 'border-status-success-border/70 bg-status-success-bg/65 text-status-success-text',
    progress: 'bg-status-success-border/90',
  },
  warning: {
    icon: AlertTriangle,
    container: 'border-status-warning-border/70 bg-status-warning-bg/92 text-status-warning-text',
    iconWrap: 'border-status-warning-border/70 bg-status-warning-bg/65 text-status-warning-text',
    progress: 'bg-status-warning-border/90',
  },
  error: {
    icon: XCircle,
    container: 'border-status-danger-border/70 bg-status-danger-bg/92 text-status-danger-text',
    iconWrap: 'border-status-danger-border/70 bg-status-danger-bg/65 text-status-danger-text',
    progress: 'bg-status-danger-border/90',
  },
}

function resolveVariant(variant) {
  if (TOAST_VARIANTS[variant]) {
    return TOAST_VARIANTS[variant]
  }

  return TOAST_VARIANTS.info
}

export default function ToastViewport({ toasts, onDismiss }) {
  if (!Array.isArray(toasts) || toasts.length === 0) {
    return null
  }

  return (
    <div className="pointer-events-none fixed right-3 top-3 z-[80] flex w-[min(92vw,26rem)] flex-col gap-2 sm:right-4 sm:top-4" aria-live="polite" aria-relevant="additions">
      {toasts.map((toast) => {
        const variant = resolveVariant(toast.variant)
        const IconGlyph = variant.icon

        return (
          <article
            key={toast.id}
            className={`pointer-events-auto relative overflow-hidden rounded-2xl border px-3 py-2.5 shadow-[var(--a26-shell-shadow)] backdrop-blur-md animate-fade-in ${variant.container}`}
            role="status"
            aria-atomic="true"
          >
            <div className="flex items-start gap-2.5">
              <span className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${variant.iconWrap}`}>
                <IconGlyph className="h-[0.875rem] w-[0.875rem]" />
              </span>

              <div className="min-w-0 flex-1">
                {toast.title ? (
                  <p className="text-sm font-semibold leading-tight">{toast.title}</p>
                ) : null}
                {toast.message ? (
                  <p className="mt-0.5 text-xs leading-relaxed opacity-95">{toast.message}</p>
                ) : null}
              </div>

              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                className="rounded-lg border border-border-subtle/55 bg-bg-card/40 p-1 text-text-secondary transition-all duration-200 hover:text-text-primary"
                aria-label="Dismiss notification"
              >
                <X className="h-[0.875rem] w-[0.875rem]" />
              </button>
            </div>

            <span
              className={`absolute bottom-0 left-0 block h-0.5 ${variant.progress}`}
              style={{ width: '100%', animation: `toastProgress ${toast.durationMs || 4200}ms linear forwards` }}
              aria-hidden="true"
            />
          </article>
        )
      })}
    </div>
  )
}
