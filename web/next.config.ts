import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  pageExtensions: ['ts', 'tsx', 'js', 'jsx'],

  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [],
  },

  experimental: {
    optimizePackageImports: ['lucide-react', 'framer-motion'],
  },

  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the browser hits same-origin
    // and we don't deal with CORS preflight on every request in dev.
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    return [{ source: '/api/:path*', destination: `${apiUrl}/:path*` }]
  },
}

export default nextConfig
