/**
 * GapAnalysisTerminal.jsx — Terminal-like execution trace panel.
 * Summary: Streams sociolinguistic routing and intervention log lines for operator diagnostics.
 */

import { useEffect, useMemo, useRef } from 'react'
import { TerminalSquare } from 'lucide-react'

function classifyLogLine(text) {
  const value = String(text || '').toLowerCase()
  if (value.includes('error') || value.includes('failed')) {
    return 'text-status-danger-text'
  }
  if (value.includes('intercept') || value.includes('override')) {
    return 'text-accent-gold'
  }
  if (value.includes('register_enforced') || value.includes('routing')) {
    return 'text-status-info-text'
  }
  if (value.includes('complete') || value.includes('success')) {
    return 'text-status-success-text'
  }
  return 'text-emerald-200/90'
}

export default function GapAnalysisTerminal({ logs = [], isFlushing = false, className = '' }) {
  const endOfLogsRef = useRef(null)

  useEffect(() => {
    endOfLogsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [logs])

  const lines = useMemo(
    () => logs.map((line, index) => ({
      id: `${index}-${line}`,
      line,
      tag: `[${String(index + 1).padStart(2, '0')}]`,
    })),
    [logs],
  )

  const containerClassName = [
    'flex h-full min-h-[10rem] flex-col overflow-hidden rounded-xl border border-border-subtle bg-slate-950 text-emerald-100 shadow-sm',
    className,
  ]
    .join(' ')
    .trim()

  return (
    <section className={containerClassName}>
      <header className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
          <TerminalSquare className="h-[0.875rem] w-[0.875rem]" />
          Gap Analysis Terminal
        </div>

        <div
          className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/70 bg-slate-900/80 px-2 py-1"
          role="status"
          aria-label={isFlushing ? 'Terminal flushing' : 'Terminal stable'}
        >
          <span className={`h-2.5 w-2.5 rounded-full bg-rose-400 ${isFlushing ? 'a26-animate-pulse' : ''}`} />
          <span className={`h-2.5 w-2.5 rounded-full bg-amber-300 ${isFlushing ? 'a26-animate-pulse' : ''}`} />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-3 py-2.5 font-mono text-xs leading-relaxed">
        {lines.length === 0 ? (
          <div className="space-y-1.5 text-emerald-200/40">
            <p>&gt; awaiting_route();</p>
            <p>&gt; warm_cache(TM, Interceptor, Observer);</p>
            <p>&gt; profiler_idle_state = true;</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {lines.map((entry) => (
              <div key={entry.id} className="grid grid-cols-[3.2rem_1fr] gap-2">
                <span className="select-none text-slate-500">{entry.tag}</span>
                <span className={classifyLogLine(entry.line)}>{entry.line}</span>
              </div>
            ))}
            <div ref={endOfLogsRef} />
          </div>
        )}
      </div>
    </section>
  )
}