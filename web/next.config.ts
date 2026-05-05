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
    //
    // Validate at config-eval time. If someone fills Vercel's env-var
    // FORM with the variable name instead of the URL (easy mistake --
    // the placeholder shows the key name), we fail loud here instead
    // of producing the cryptic "destination does not start with /,
    // http://, or https://" error from Vercel's rewrite validator.
    const raw = process.env.NEXT_PUBLIC_API_URL ?? ''
    const apiUrl = /^https?:\/\//.test(raw) ? raw : 'http://localhost:8000'
    if (raw && !/^https?:\/\//.test(raw)) {
      // eslint-disable-next-line no-console
      console.warn(
        `[next.config] NEXT_PUBLIC_API_URL is "${raw}" — not an http(s) URL. ` +
        `Falling back to ${apiUrl}. Did you paste the variable NAME into the VALUE field?`,
      )
    }
    return [{ source: '/api/:path*', destination: `${apiUrl}/:path*` }]
  },
}

export default nextConfig
