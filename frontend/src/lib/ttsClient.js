import axios from 'axios'
import { withApiKeyHeaders } from './apiAuth'

const DEFAULT_TTS_VOICE_BY_LANG = {
  es: 'es-ES-AlvaroNeural',
}

let activeController = null
let activeAudio = null
let activeObjectUrl = null

function cleanupPlayback() {
  if (activeAudio) {
    activeAudio.pause()
    activeAudio.src = ''
    activeAudio = null
  }

  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl)
    activeObjectUrl = null
  }

  activeController = null
}

async function readBlobError(blob) {
  if (!blob || typeof blob.text !== 'function') {
    return 'Text-to-speech failed.'
  }

  try {
    const text = await blob.text()
    const parsed = JSON.parse(text)
    return parsed?.error || parsed?.errors?.text?.[0] || 'Text-to-speech failed.'
  } catch {
    return 'Text-to-speech failed.'
  }
}

export function stopEdgeTtsPlayback() {
  if (activeController) {
    activeController.abort()
  }
  cleanupPlayback()
}

export async function speakWithEdgeTts({ apiUrl, text, langCode = 'en', voice = '' }) {
  const trimmedText = (text || '').trim()
  if (!trimmedText) return null
  if (!apiUrl) throw new Error('API URL is not configured.')

  stopEdgeTtsPlayback()

  const controller = new AbortController()
  activeController = controller

  try {
    const normalizedLang = String(langCode || 'en').toLowerCase()
    const resolvedVoice = voice || DEFAULT_TTS_VOICE_BY_LANG[normalizedLang] || ''

    const response = await axios.post(
      `${apiUrl}/tts/`,
      {
        text: trimmedText,
        lang_code: normalizedLang,
        voice: resolvedVoice,
      },
      {
        responseType: 'blob',
        headers: withApiKeyHeaders(),
        signal: controller.signal,
        timeout: 45000,
      },
    )

    if (activeController !== controller) return null

    activeObjectUrl = URL.createObjectURL(response.data)
    activeAudio = new Audio(activeObjectUrl)
    activeAudio.addEventListener('ended', cleanupPlayback, { once: true })
    activeAudio.addEventListener('error', cleanupPlayback, { once: true })

    await activeAudio.play()

    return {
      voice: response.headers['x-tts-voice'] || null,
    }
  } catch (error) {
    if (error?.code === 'ERR_CANCELED') {
      throw error
    }

    const message = error?.response?.data
      ? await readBlobError(error.response.data)
      : (error?.message || 'Text-to-speech failed.')

    cleanupPlayback()
    throw new Error(message)
  }
}