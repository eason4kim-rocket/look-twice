import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: { default: "Look Twice — Active Evidence Assurance", template: "%s · Look Twice" },
  description: "A Purify-powered active evidence assurance layer for Physical AI on AMD GPU.",
  openGraph: {
    type: "website",
    title: "Look Twice — Active Evidence Assurance",
    description:
      "A robot should not act on evidence it cannot defend. Watch the 30-second Purify-qualified repair loop.",
    images: [
      {
        url: "/media/look-twice-replay-30s.poster.webp",
        width: 1920,
        height: 1080,
        alt: "Look Twice recorded trajectory replay",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Look Twice — Active Evidence Assurance",
    description:
      "Claim → Purify → active evidence repair → qualified physical action.",
    images: ["/media/look-twice-replay-30s.poster.webp"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${inter.variable} ${mono.variable}`}>{children}</body></html>;
}
