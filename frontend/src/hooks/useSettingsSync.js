/**
 * useSettingsSync.js — Settings event synchronization hook.
 * Summary: Listens for local storage and custom settings events, then dispatches normalized updates to callers.
 */

import { useEffect } from 'react'
import {
  loadSettings,
  SETTINGS_STORAGE_KEY,
  SETTINGS_UPDATED_EVENT,
} from '../lib/settings'

export function useSettingsSync(onSettingsChange) {
  useEffect(() => {
    if (typeof onSettingsChange !== 'function') {
      return undefined
    }

    const applySettings = (nextSettings) => {
      onSettingsChange(nextSettings)
    }

    const handleSettingsUpdated = (event) => {
      applySettings(event?.detail ?? loadSettings())
    }

    const handleStorage = (event) => {
      if (event.key && event.key !== SETTINGS_STORAGE_KEY) {
        return
      }

      applySettings(loadSettings())
    }

    window.addEventListener(SETTINGS_UPDATED_EVENT, handleSettingsUpdated)
    window.addEventListener('storage', handleStorage)

    return () => {
      window.removeEventListener(SETTINGS_UPDATED_EVENT, handleSettingsUpdated)
      window.removeEventListener('storage', handleStorage)
    }
  }, [onSettingsChange])
}
