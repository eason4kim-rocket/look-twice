"use client";

import Link from "next/link";
import { createContext, useContext, useState } from "react";

type Language = "en" | "zh";
const LanguageContext = createContext<{language: Language; setLanguage: (value: Language) => void}>({language: "en", setLanguage: () => {}});
export const useLanguage = () => useContext(LanguageContext);

export function SiteShell({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");
  const zh = language === "zh";
  return <LanguageContext.Provider value={{language, setLanguage}}>
    <div className="site-shell">
      <header className="topbar">
        <Link className="brand" href="/"><span className="brand-mark">LT</span><span>LOOK TWICE<small>ACTIVE EVIDENCE ASSURANCE</small></span></Link>
        <nav><Link href="/console">{zh?"控制台":"CONSOLE"}</Link><Link href="/results">{zh?"结果":"RESULTS"}</Link><Link href="/reproduce">{zh?"复现":"REPRODUCE"}</Link></nav>
        <div className="top-actions"><span className="status-pill"><i /> {zh?"回放就绪":"REPLAY READY"}</span><button onClick={() => setLanguage(language === "en" ? "zh" : "en")}>{language === "en" ? "中" : "EN"}</button></div>
      </header>
      {children}
      <footer><div className="brand compact"><span className="brand-mark">LT</span><span>LOOK TWICE</span></div><p>Recorded AMD GPU evidence · Simulation only · Frozen candidate artifact</p><span>APACHE-2.0</span></footer>
    </div>
  </LanguageContext.Provider>;
}
