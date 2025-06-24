// next.config.ts - Otimizado sem Warnings
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker optimization
  output: 'standalone',
  
  // Image optimization
  images: {
    formats: ['image/webp', 'image/avif'],
    minimumCacheTTL: 60,
  },

  // Server external packages (Next.js 15 syntax)
  serverExternalPackages: ['sharp'],

  // Disable telemetry
  env: {
    NEXT_TELEMETRY_DISABLED: '1',
  },

  // Security headers (otimização de segurança)
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ];
  },

  // Health check endpoint
  async rewrites() {
    return [
      {
        source: '/health',
        destination: '/api/health',
      },
    ];
  },

  // Otimizações de build SEM usar webpack config (evita warning)
  productionBrowserSourceMaps: false,
  poweredByHeader: false,
  compress: true,
};

export default nextConfig;