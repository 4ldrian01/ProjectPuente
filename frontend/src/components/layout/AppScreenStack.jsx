/**
 * AppScreenStack.jsx — Screen composition layer for application routes.
 * Summary: Mounts and toggles major screens while preserving hidden-screen state and transition behavior.
 */

import TranslateScreen from '../screens/TranslateScreen'
import WikiVozScreen from '../screens/WikiVozScreen'
import SettingsScreen from '../screens/SettingsScreen'
import SystemEvaluationScreen from '../screens/SystemEvaluationScreen'
import DatabaseAdminScreen from '../screens/DatabaseAdminScreen'
import ActivityLogsScreen from '../screens/ActivityLogsScreen'

export default function AppScreenStack({
  activeScreen,
  mountedScreens,
  onTranslate,
  translatedText,
  loading,
  error,
  wikiData,
  wikiMetadata,
  gapAnalysisData,
  btvlData,
  apiUrl,
  health,
  clientApiKeyConfigured,
  translationMeta,
  theme,
  onRefreshHealth,
  notify,
}) {
  return (
    <div className="mx-auto w-full max-w-7xl">
      <div
        className={`${activeScreen === 'translate' ? 'flex' : 'hidden'} min-h-[calc(100vh-8rem)] flex-col`}
        aria-hidden={activeScreen !== 'translate'}
      >
        <TranslateScreen
          isActive={activeScreen === 'translate'}
          onTranslate={onTranslate}
          translatedText={translatedText}
          loading={loading}
          error={error}
          apiReady={health.backendUp && health.nllbLoaded && (!health.apiKeyRequired || clientApiKeyConfigured)}
          wikiData={wikiData}
          wikiMetadata={wikiMetadata}
          gapAnalysisData={gapAnalysisData}
          btvlData={btvlData}
          apiUrl={apiUrl}
          backendUp={health.backendUp}
          ttsAvailable={health.ttsAvailable}
          loraAdapters={health.loraAdapters}
          nllbLoaded={health.nllbLoaded}
          apiKeyRequired={health.apiKeyRequired}
          clientApiKeyConfigured={clientApiKeyConfigured}
          translationEngine={health.engine}
          translationMeta={translationMeta}
          notify={notify}
        />
      </div>

      {mountedScreens['wiki-voz'] ? (
        <div
          className={`${activeScreen === 'wiki-voz' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
          aria-hidden={activeScreen !== 'wiki-voz'}
        >
          <WikiVozScreen
            apiUrl={apiUrl}
            backendUp={health.backendUp}
            ttsAvailable={health.ttsAvailable}
            notify={notify}
          />
        </div>
      ) : null}

      {mountedScreens['activity-logs'] ? (
        <div
          className={`${activeScreen === 'activity-logs' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
          aria-hidden={activeScreen !== 'activity-logs'}
        >
          <ActivityLogsScreen
            apiUrl={apiUrl}
            backendUp={health.backendUp}
            notify={notify}
            isActive={activeScreen === 'activity-logs'}
          />
        </div>
      ) : null}

      {mountedScreens.evaluation ? (
        <div
          className={`${activeScreen === 'evaluation' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
          aria-hidden={activeScreen !== 'evaluation'}
        >
          <SystemEvaluationScreen />
        </div>
      ) : null}

      {mountedScreens['db-admin'] ? (
        <div
          className={`${activeScreen === 'db-admin' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
          aria-hidden={activeScreen !== 'db-admin'}
        >
          <DatabaseAdminScreen apiUrl={apiUrl} notify={notify} />
        </div>
      ) : null}

      {mountedScreens.settings ? (
        <div
          className={`${activeScreen === 'settings' ? 'flex' : 'hidden'} screen-transition-in min-h-[calc(100vh-8rem)] flex-col`}
          aria-hidden={activeScreen !== 'settings'}
        >
          <SettingsScreen
            health={health}
            onRefreshHealth={onRefreshHealth}
            activeTheme={theme}
          />
        </div>
      ) : null}
    </div>
  )
}
