import { Activity, BrainCircuit, Gauge, ShieldCheck, Sparkles } from 'lucide-react'
import * as echarts from 'echarts/core'
import ReactEChartsCore from 'echarts-for-react/lib/core.js'
import { PieChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  PieChart,
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

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

const INTERCEPT_TOTAL = INTERCEPT_CONCURRENCE_DATA.reduce((sum, entry) => sum + entry.value, 0)

const INTERCEPT_CHART_OPTION = {
  animationDuration: 700,
  animationEasing: 'cubicOut',
  color: INTERCEPT_CONCURRENCE_DATA.map((entry) => entry.fill),
  tooltip: {
    trigger: 'item',
    backgroundColor: '#111827',
    borderColor: '#374151',
    borderWidth: 1,
    textStyle: {
      color: '#f9fafb',
      fontSize: 12,
      fontWeight: 500,
    },
    formatter: (params) => `${params.name}<br/>Share: ${params.value}%`,
  },
  legend: {
    bottom: 0,
    icon: 'circle',
    textStyle: {
      color: '#9ca3af',
      fontSize: 12,
    },
  },
  series: [
    {
      name: 'Intercept Share',
      type: 'pie',
      radius: ['52%', '78%'],
      center: ['50%', '43%'],
      padAngle: 3,
      avoidLabelOverlap: true,
      itemStyle: {
        borderColor: '#0f172a',
        borderWidth: 2,
      },
      label: {
        show: false,
      },
      data: INTERCEPT_CONCURRENCE_DATA.map((entry) => ({
        value: entry.value,
        name: entry.name,
      })),
      emphasis: {
        scale: true,
        itemStyle: {
          shadowBlur: 12,
          shadowColor: 'rgba(0, 0, 0, 0.35)',
        },
      },
    },
  ],
}

const LENGTH_INFERENCE_CHART_OPTION = {
  animationDuration: 800,
  animationEasing: 'quarticOut',
  tooltip: {
    trigger: 'axis',
    backgroundColor: '#111827',
    borderColor: '#374151',
    borderWidth: 1,
    textStyle: {
      color: '#f9fafb',
      fontSize: 12,
      fontWeight: 500,
    },
    axisPointer: {
      type: 'line',
      lineStyle: {
        color: '#d946ef',
        width: 1,
      },
    },
    formatter: (params) => {
      const point = params?.[0]
      if (!point) {
        return ''
      }

      return `Length: ${point.axisValue} tokens<br/>Inference Time: ${point.data} ms`
    },
  },
  grid: {
    top: 12,
    right: 20,
    bottom: 52,
    left: 46,
  },
  xAxis: {
    type: 'category',
    name: 'Length (tokens)',
    nameLocation: 'middle',
    nameGap: 30,
    boundaryGap: false,
    axisLine: {
      lineStyle: {
        color: '#374151',
      },
    },
    axisTick: {
      show: false,
    },
    axisLabel: {
      color: '#9ca3af',
      fontSize: 12,
    },
    data: LENGTH_INFERENCE_DATA.map((point) => point.lengthTokens),
  },
  yAxis: {
    type: 'value',
    name: 'Inference ms',
    nameLocation: 'middle',
    nameGap: 42,
    axisLine: {
      show: false,
    },
    axisTick: {
      show: false,
    },
    axisLabel: {
      color: '#9ca3af',
      fontSize: 12,
    },
    splitLine: {
      lineStyle: {
        type: 'dashed',
        color: 'rgba(107, 114, 128, 0.35)',
      },
    },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 7,
      lineStyle: {
        color: '#d946ef',
        width: 3,
      },
      itemStyle: {
        color: '#111827',
        borderColor: '#d946ef',
        borderWidth: 2,
      },
      areaStyle: {
        color: 'rgba(217, 70, 239, 0.14)',
      },
      data: LENGTH_INFERENCE_DATA.map((point) => point.inferenceMs),
    },
  ],
}

export default function SystemEvaluationScreen() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="a26-surface relative overflow-hidden p-5 md:p-6">
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
            <span className="a26-chip"><Activity className="h-3.5 w-3.5" /> Live Dashboard</span>
            <span className="a26-chip"><Gauge className="h-3.5 w-3.5" /> Edge Inference Signal</span>
            <span className="a26-chip"><BrainCircuit className="h-3.5 w-3.5" /> Sociolinguistic Focus</span>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {KPI_CARDS.map((card) => (
          <article
            key={card.key}
            className="a26-surface p-5"
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
        <article className="a26-surface p-4 md:p-5">
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-text-secondary">Sociolinguistic Intercept Concurrence</h3>
          <p className="mt-1 text-sm text-text-secondary">False Cognates vs Politeness Gaps vs Idioms</p>

          <div className="relative mt-4 h-[300px]">
            <ReactEChartsCore
              echarts={echarts}
              option={INTERCEPT_CHART_OPTION}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
            />

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-black text-text-primary">{INTERCEPT_TOTAL}%</span>
              <span className="text-[11px] uppercase tracking-[0.12em] text-text-secondary">Intercept Share</span>
            </div>
          </div>
        </article>

        <article className="a26-surface p-4 md:p-5">
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-text-secondary">Translation Length vs Inference Time</h3>
          <p className="mt-1 text-sm text-text-secondary">Mock trendline from local edge inference samples</p>

          <div className="mt-4 h-[300px]">
            <ReactEChartsCore
              echarts={echarts}
              option={LENGTH_INFERENCE_CHART_OPTION}
              style={{ height: '100%', width: '100%' }}
              opts={{ renderer: 'canvas' }}
            />
          </div>
        </article>
      </section>
    </div>
  )
}
