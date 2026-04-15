/**
 * useDebouncedValue.js — Generic value debouncing hook.
 * Summary: Emits a delayed mirror of rapidly changing state to reduce fetch churn and UI thrash.
 */

import { useEffect, useState } from 'react'

export function useDebouncedValue(value, delayMs = 250) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delayMs)

    return () => clearTimeout(timer)
  }, [delayMs, value])

  return debouncedValue
}
