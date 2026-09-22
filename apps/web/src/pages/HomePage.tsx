import { getHealth } from '@schemio/api-client'
import { Placeholder } from '@schemio/ui'
import { useCallback, useEffect, useRef, useState } from 'react'

type ApiStatus = 'checking' | 'ok' | 'unreachable'

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const controllerRef = useRef<AbortController | null>(null)

  const checkHealth = useCallback((signal?: AbortSignal) => {
    setApiStatus('checking')
    return getHealth({ signal })
      .then((health) => setApiStatus(health.status === 'ok' ? 'ok' : 'unreachable'))
      .catch(() => {
        if (!signal?.aborted) setApiStatus('unreachable')
      })
  }, [])

  const load = useCallback(() => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    void checkHealth(controller.signal)
  }, [checkHealth])

  useEffect(() => {
    load()
    return () => controllerRef.current?.abort()
  }, [load])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-bold">Schemio — Foundation</h1>
      <Placeholder label="packages/ui is linked" />
      <p aria-live="polite">api: {apiStatus}</p>
      {apiStatus === 'unreachable' && (
        <button type="button" onClick={load}>
          Retry
        </button>
      )}
    </main>
  )
}
