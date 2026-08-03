import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { LanguageProvider } from "./components/SiteShell";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://look-twice-evidence-console.eason1319.workers.dev"),
  title: { default: "Look Twice — Active Evidence Assurance", template: "%s · Look Twice" },
  description: "A Purify-powered active evidence assurance layer for Physical AI on AMD GPU.",
  alternates: { canonical: "/" },
  openGraph: {
    url: "https://look-twice-evidence-console.eason1319.workers.dev/",
    type: "website",
    title: "Look Twice — Active Evidence Assurance",
    description:
      "A robot should not act on evidence it cannot defend. Watch the 30-second Purify-qualified repair loop.",
    images: [
      {
        url: "https://look-twice-evidence-console.eason1319.workers.dev/og.png",
        width: 1730,
        height: 909,
        alt: "Look Twice active evidence assurance for Track 3 Physical AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Look Twice — Active Evidence Assurance",
    description:
      "Claim → Purify → active evidence repair → qualified physical action.",
    images: ["https://look-twice-evidence-console.eason1319.workers.dev/og.png"],
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
