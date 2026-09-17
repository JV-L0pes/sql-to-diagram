import { useEffect, useState } from 'react'
import { Placeholder } from '@sql-to-diagram/ui'
import { getHealth } from '@sql-to-diagram/api-client'

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<string>('checking...')

  useEffect(() => {
    getHealth()
      .then((health) => setApiStatus(health.status))
      .catch(() => setApiStatus('unreachable'))
  }, [])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-bold">SQL to Diagram — Foundation</h1>
      <Placeholder label="packages/ui is linked" />
      <p>api: {apiStatus}</p>
    </main>
  )
}
