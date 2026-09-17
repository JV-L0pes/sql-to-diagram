import type { paths } from './schema'

export type HealthResponse = paths['/api/health']['get']['responses'][200]['content']['application/json']

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch('/api/health')
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }
  return response.json() as Promise<HealthResponse>
}
