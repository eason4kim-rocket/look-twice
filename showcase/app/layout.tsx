import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { LanguageProvider } from "./components/SiteShell";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://eason4kim-rocket.github.io"),
  title: { default: "Look Twice — Action-Ready Evidence for Warehouse Robots", template: "%s · Look Twice" },
  description:
    "Look Twice checks whether warehouse evidence is independent, calibrated, and sufficient for the next action, then actively repairs what is missing on AMD Radeon and ROCm.",
  alternates: { canonical: "/" },
  openGraph: {
    url: "https://eason4kim-rocket.github.io/",
    type: "website",
    title: "Look Twice — Action-Ready Evidence for Warehouse Robots",
    description:
      "Physical-root lineage, Action Contracts, and BeliefGap-driven repair. In a preregistered 30-world simulation, active went direct in 29/30 worlds versus passive 0/30.",
    images: [
      {
        url: "https://eason4kim-rocket.github.io/og-contract-progress.png",
        width: 1726,
        height: 911,
        alt: "Look Twice warehouse action assurance on AMD Radeon and ROCm simulation",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Look Twice — Action-Ready Evidence for Warehouse Robots",
    description:
      "Physical-root lineage, Action Contracts, and active evidence repair: 29/30 active direct versus 0/30 passive in a preregistered warehouse simulation.",
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
