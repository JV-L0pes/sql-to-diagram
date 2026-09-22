import type { paths } from './schema'

export type HealthResponse =
  paths['/api/health']['get']['responses'][200]['content']['application/json']

export async function getHealth(options: { signal?: AbortSignal } = {}): Promise<HealthResponse> {
  const response = await fetch('/api/health', { signal: options.signal })
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }
  return response.json() as Promise<HealthResponse>
}
