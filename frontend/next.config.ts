import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `standalone` : le build embarque son propre serveur Node minimal.
  // C'est ce qui permet une image Docker de ~150 Mo au lieu de ~1 Go.
  output: "standalone",
  reactStrictMode: true,
};

export default nextConfig;
