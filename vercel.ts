import { routes, type VercelConfig } from '@vercel/config/v1'

export const config: VercelConfig = {
  buildCommand: 'pnpm --filter web build',
  outputDirectory: 'apps/web/dist',
  rewrites: [routes.rewrite('/api/(.*)', '/api/index.py')],
}
