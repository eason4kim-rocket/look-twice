import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/media/:path*.mp4",
        headers: [{ key: "Content-Type", value: "video/mp4" }],
      },
    ];
  },
};

export default nextConfig;
