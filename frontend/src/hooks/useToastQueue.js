/**
 * useToastQueue.js — Toast lifecycle state hook.
 * Summary: Manages queueing, auto-dismiss timing, and explicit dismissal for transient notifications.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

function buildToastId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function useToastQueue({ maxToasts = 4, defaultDurationMs = 4200 } = {}) {
  const [toasts, setToasts] = useState([])
  const timersRef = useRef(new Map())

  const dismissToast = useCallback((toastId) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== toastId))

    const timerId = timersRef.current.get(toastId)
    if (timerId) {
      clearTimeout(timerId)
      timersRef.current.delete(toastId)
    }
  }, [])

  const showToast = useCallback((payload = {}) => {
    const {
      title = '',
      message = '',
      variant = 'info',
      durationMs = defaultDurationMs,
    } = payload

    const id = buildToastId()

    setToasts((previous) => ([
      ...previous.slice(-(maxToasts - 1)),
      {
        id,
        title,
        message,
        variant,
        durationMs,
      },
    ]))

    const timerId = window.setTimeout(() => {
      dismissToast(id)
    }, durationMs)

    timersRef.current.set(id, timerId)
  }, [defaultDurationMs, dismissToast, maxToasts])

  useEffect(() => {
    const timers = timersRef.current

    return () => {
      timers.forEach((timerId) => clearTimeout(timerId))
      timers.clear()
    }
  }, [])

  return {
    toasts,
    showToast,
    dismissToast,
  }
}
