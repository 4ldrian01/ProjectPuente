/**
 * main.jsx — Frontend bootstrap entry point.
 * Summary: Initializes React root, mounts application shell, and wires global runtime providers.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { applyThemeToDocument, loadSettings } from './lib/settings'

const initialSettings = loadSettings()
applyThemeToDocument(initialSettings.theme)

if (typeof window !== 'undefined') {
  // Recover from stale hashed bundles (common after deploy + active SW cache).
  window.addEventListener('vite:preloadError', (event) => {
    event.preventDefault()
    window.location.reload()
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
