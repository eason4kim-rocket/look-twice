import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { LanguageProvider } from "./components/SiteShell";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://eason4kim-rocket.github.io"),
  title: { default: "Look Twice — Active Evidence Assurance", template: "%s · Look Twice" },
  description: "A Purify-powered active evidence assurance layer for Physical AI on AMD GPU.",
  alternates: { canonical: "/" },
  openGraph: {
    url: "https://eason4kim-rocket.github.io/",
    type: "website",
    title: "Look Twice — Active Evidence Assurance",
    description:
      "A robot should not act on evidence it cannot defend. See the verified repair loop and two completed rigid-body scene shards.",
    images: [
      {
        url: "https://eason4kim-rocket.github.io/og-two-shard.png",
        width: 1728,
        height: 910,
        alt: "Look Twice two completed rigid-body scene shards for Track 3 Physical AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Look Twice — Active Evidence Assurance",
    description:
      "Claim → Purify → active repair → qualified action, backed by two completed rigid-body scene shards.",
    images: ["https://eason4kim-rocket.github.io/og-two-shard.png"],
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
