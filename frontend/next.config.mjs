/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
      },
    ],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            // SHA-256 hash covers the inline theme-init script in layout.tsx.
            // If that script changes, recompute: echo -n '<script>' | openssl dgst -sha256 -binary | openssl base64
            value: [
              "default-src 'self'",
              "script-src 'self' 'sha256-X8XN7IK+5noayWSxdVJz3QFvCIeNDi1kOQDj/IIPsCg='",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: https://lh3.googleusercontent.com",
              "font-src 'self'",
              `connect-src 'self' https://*.supabase.co wss://*.supabase.co https://bahtzang-backend-production.up.railway.app${process.env.NODE_ENV !== "production" ? " http://localhost:* ws://localhost:*" : ""}`,
              "form-action 'self'",
              "base-uri 'self'",
              "object-src 'none'",
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
