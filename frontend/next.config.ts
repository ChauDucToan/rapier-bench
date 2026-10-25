import type { NextConfig } from "next";

// Note: Backend API base URL is configured via process.env.NEXT_PUBLIC_API_BASE_URL
const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
