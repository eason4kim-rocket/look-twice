import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { LanguageProvider } from "./components/SiteShell";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://eason4kim-rocket.github.io"),
  title: { default: "Look Twice — Contract-Aware Active Perception", template: "%s · Look Twice" },
  description:
    "Frozen RGB-D perception, conformal action qualification and contract-aware active sensing on AMD GPU, backed by publicly preregistered simulation evidence.",
  alternates: { canonical: "/" },
  openGraph: {
    url: "https://eason4kim-rocket.github.io/",
    type: "website",
    title: "Look Twice — Contract-Aware Active Perception",
    description:
      "20/20 direct with zero unsafe events while reducing scout path 40.26%, team path 15.03% and physical captures 27.54% in a publicly preregistered same-generator simulation challenge.",
    images: [
      {
        url: "https://eason4kim-rocket.github.io/og-contract-progress.png",
        width: 1726,
        height: 911,
        alt: "Look Twice contract-aware active perception results on AMD GPU simulation",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Look Twice — Contract-Aware Active Perception",
    description:
      "20/20 direct, zero unsafe, with lower scout path, team path and physical capture burden in a publicly preregistered AMD GPU simulation challenge.",
    images: ["https://eason4kim-rocket.github.io/og-contract-progress.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${mono.variable}`}>
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
