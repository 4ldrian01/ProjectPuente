/**
 * useBackendHealth.js — Backend health polling hook.
 * Summary: Tracks connectivity, model readiness, TTS availability, and request latency on a timed interval.
 */

import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'

const DEFAULT_HEALTH = {
  checking: true,
  backendUp: false,
  nllbLoaded: false,
  loraAdapters: [],
  apiKeyRequired: false,
  ttsAvailable: false,
  ttsEngine: 'unavailable',
  engine: 'unknown',
}

const OFFLINE_HEALTH = {
  checking: false,
  backendUp: false,
  nllbLoaded: false,
  loraAdapters: [],
  apiKeyRequired: false,
  ttsAvailable: false,
  ttsEngine: 'offline',
  engine: 'offline',
}

export function useBackendHealth(apiUrl) {
  const [health, setHealth] = useState(DEFAULT_HEALTH)
  const [latencyMs, setLatencyMs] = useState(null)

  const refreshHealth = useCallback(async () => {
    const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
    setHealth((previous) => ({ ...previous, checking: true }))

    try {
      const { data } = await axios.get(`${apiUrl}/health/`, { timeout: 10000 })
      const completedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
      setLatencyMs(Math.max(0, completedAt - startedAt))

      setHealth({
        checking: false,
        backendUp: true,
        nllbLoaded: Boolean(data.nllb_loaded),
        loraAdapters: data.lora_adapters || [],
        apiKeyRequired: Boolean(data.api_key_required),
        ttsAvailable: Boolean(data.tts_available),
        ttsEngine: data.tts_engine || 'unavailable',
        engine: data.engine || 'unknown',
        _lastChecked: Date.now(),
      })
    } catch {
      setLatencyMs(null)
      setHealth({
        ...OFFLINE_HEALTH,
        _lastChecked: Date.now(),
      })
    }
  }, [apiUrl])

  useEffect(() => {
    refreshHealth()
    const interval = setInterval(refreshHealth, 30000)
    return () => clearInterval(interval)
  }, [refreshHealth])

  return {
    health,
    latencyMs,
    refreshHealth,
  }
}
