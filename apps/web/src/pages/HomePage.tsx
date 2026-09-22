import { getHealth } from '@schemio/api-client'
import { Placeholder } from '@schemio/ui'
import { useCallback, useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'ok' | 'unreachable'

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')

  const checkHealth = useCallback((signal?: AbortSignal) => {
    setApiStatus('checking')
    return getHealth({ signal })
      .then((health) => setApiStatus(health.status === 'ok' ? 'ok' : 'unreachable'))
      .catch(() => {
        if (!signal?.aborted) setApiStatus('unreachable')
      })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    checkHealth(controller.signal)
    return () => controller.abort()
  }, [checkHealth])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-bold">Schemio — Foundation</h1>
      <Placeholder label="packages/ui is linked" />
      <p aria-live="polite">api: {apiStatus}</p>
      {apiStatus === 'unreachable' && (
        <button type="button" onClick={() => checkHealth()}>
          Retry
        </button>
      )}
    </main>
  )
}
