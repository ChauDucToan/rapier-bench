import type { NextConfig } from "next";

// Note: Backend API base URL is configured via process.env.NEXT_PUBLIC_API_BASE_URL
const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    // Tailwind v4 integration: @tailwindcss/turbopack is a webpack-style
    // loader. Without it, `next build` emits only the raw globals.css (~226
    // bytes) and every utility class in the UI silently loses its styles.
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
      },
    },
  },
};

export default nextConfig;
