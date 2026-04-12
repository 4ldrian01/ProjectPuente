import { Activity, BrainCircuit, Gauge, ShieldCheck, Sparkles } from 'lucide-react'
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const KPI_CARDS = [
  {
    key: 'bleu',
    label: 'BLEU Score',
    value: '38.2',
    description: 'Bilingual Evaluation Understudy',
    icon: Sparkles,
    accent: 'text-accent-magenta bg-accent-magenta/10 border-accent-magenta/30',
  },
  {
    key: 'chrf',
    label: 'chrF++ Score',
    value: '56.4',
    description: 'Character n-gram F-score',
    icon: ShieldCheck,
    accent: 'text-accent-gold bg-accent-gold/10 border-accent-gold/30',
  },
]

const INTERCEPT_CONCURRENCE_DATA = [
  { name: 'False Cognates', value: 45, fill: '#ef4444' },
  { name: 'Politeness Gaps', value: 35, fill: '#f59e0b' },
  { name: 'Idioms', value: 20, fill: '#3b82f6' },
]

const LENGTH_INFERENCE_DATA = [
  { lengthTokens: 8, inferenceMs: 320 },
  { lengthTokens: 14, inferenceMs: 460 },
  { lengthTokens: 21, inferenceMs: 640 },
  { lengthTokens: 29, inferenceMs: 870 },
  { lengthTokens: 38, inferenceMs: 1120 },
  { lengthTokens: 46, inferenceMs: 1390 },
  { lengthTokens: 55, inferenceMs: 1650 },
]

function DashboardTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) {
    return null
  }

  return (
    <div className="rounded-lg border border-border-subtle bg-bg-card px-3 py-2 text-xs text-text-primary shadow-xl">
      <p className="font-semibold text-text-primary">Length: {label} tokens</p>
      <p className="mt-1 text-text-secondary">Inference Time: <span className="text-text-primary">{payload[0].value} ms</span></p>
    </div>
  )
}

function PieTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) {
    return null
  }

  const item = payload[0]

  return (
    <div className="rounded-lg border border-border-subtle bg-bg-card px-3 py-2 text-xs text-text-primary shadow-xl">
      <p className="font-semibold text-text-primary">{item.name}</p>
      <p className="mt-1 text-text-secondary">Share: <span className="text-text-primary">{item.value}%</span></p>
    </div>
  )
}

export default function SystemEvaluationScreen() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header
        className="a26-surface a26-intro-enter relative overflow-hidden p-5 md:p-6"
        style={{ '--a26-intro-delay': '0ms' }}
      >
        <div className="pointer-events-none absolute -right-8 -top-8 h-40 w-40 rounded-full bg-accent-magenta/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-10 left-8 h-32 w-32 rounded-full bg-accent-gold/10 blur-3xl" />

        <div className="relative">
          <p className="a26-subtitle">System Evaluation</p>
          <h2 className="a26-hero-title mt-1 font-semibold text-text-primary">
            Sociolinguistic Quality Observatory
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-secondary">
            Runtime-aligned evaluation cockpit blending quality metrics, intercept diagnostics,
            and inference behavior trends into one visual control layer.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="a26-chip a26-intro-enter" style={{ '--a26-intro-delay': '40ms' }}><Activity className="h-3.5 w-3.5" /> Live Dashboard</span>
            <span className="a26-chip a26-intro-enter" style={{ '--a26-intro-delay': '70ms' }}><Gauge className="h-3.5 w-3.5" /> Edge Inference Signal</span>
            <span className="a26-chip a26-intro-enter" style={{ '--a26-intro-delay': '100ms' }}><BrainCircuit className="h-3.5 w-3.5" /> Sociolinguistic Focus</span>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {KPI_CARDS.map((card, index) => (
          <article
            key={card.key}
            className="a26-surface a26-row-intro p-5"
            style={{ '--a26-row-delay': `${index * 26}ms` }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">{card.label}</p>
                <p className="mt-2 text-4xl font-black tracking-tight text-text-primary">{card.value}</p>
              </div>

              <span className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl border ${card.accent}`}>
                <card.icon className="h-4.5 w-4.5" />
              </span>
            </div>

            <p className="mt-2 text-sm text-text-secondary">{card.description}</p>

            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-bg-elevated">
              <span
                className="block h-full rounded-full bg-accent-magenta/70"
                style={{ width: `${Math.min(100, Number(card.value) || 0)}%` }}
              />
            </div>
          </article>
        ))}
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.35fr]">
        <article
          className="a26-surface a26-intro-enter p-4 md:p-5"
          style={{ '--a26-intro-delay': '110ms' }}
        >
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-text-secondary">Sociolinguistic Intercept Concurrence</h3>
          <p className="mt-1 text-sm text-text-secondary">False Cognates vs Politeness Gaps vs Idioms</p>

          <div className="relative mt-4 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={INTERCEPT_CONCURRENCE_DATA}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={72}
                  outerRadius={108}
                  paddingAngle={3}
                  stroke="none"
                >
                  {INTERCEPT_CONCURRENCE_DATA.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip content={<PieTooltip />} />
                <Legend verticalAlign="bottom" height={28} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-black text-text-primary">100%</span>
              <span className="text-[11px] uppercase tracking-[0.12em] text-text-secondary">Intercept Share</span>
            </div>
          </div>
        </article>

        <article
          className="a26-surface a26-intro-enter p-4 md:p-5"
          style={{ '--a26-intro-delay': '140ms' }}
        >
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-text-secondary">Translation Length vs Inference Time</h3>
          <p className="mt-1 text-sm text-text-secondary">Mock trendline from local edge inference samples</p>

          <div className="mt-4 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={LENGTH_INFERENCE_DATA} margin={{ top: 10, right: 16, left: 0, bottom: 6 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--puente-border-subtle)" opacity={0.45} />
                <XAxis
                  dataKey="lengthTokens"
                  tick={{ fill: 'var(--puente-text-secondary)', fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: 'var(--puente-border-subtle)' }}
                  label={{ value: 'Length (tokens)', position: 'insideBottom', offset: -4, fill: 'var(--puente-text-secondary)', fontSize: 11 }}
                />
                <YAxis
                  tick={{ fill: 'var(--puente-text-secondary)', fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: 'var(--puente-border-subtle)' }}
                  label={{ value: 'Inference ms', angle: -90, position: 'insideLeft', fill: 'var(--puente-text-secondary)', fontSize: 11 }}
                />
                <Tooltip content={<DashboardTooltip />} />
                <Line
                  type="monotone"
                  dataKey="inferenceMs"
                  stroke="#d946ef"
                  strokeWidth={2.8}
                  dot={{ r: 3, strokeWidth: 1.5, fill: '#121212' }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>
    </div>
  )
}
