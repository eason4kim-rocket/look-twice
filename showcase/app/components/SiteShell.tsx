"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useState } from "react";

type Language = "en" | "zh";
const LanguageContext = createContext<{language: Language; setLanguage: (value: Language) => void}>({language: "en", setLanguage: () => {}});
export const useLanguage = () => useContext(LanguageContext);

export function SiteShell({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");
  const pathname = usePathname();
  const consoleMode = pathname === "/console";
  const zh = language === "zh";
  return <LanguageContext.Provider value={{language, setLanguage}}>
    <div className={`site-shell ${consoleMode ? "shell-console" : "shell-marketing"}`}>
      <header className="topbar">
        <Link className="brand" href="/">
          <span className="brand-symbol" aria-hidden="true"><i/><i/></span>
          <span>Look Twice<small>Active evidence assurance</small></span>
        </Link>
        <nav aria-label={zh ? "主导航" : "Primary navigation"}>
          <Link className={pathname === "/" ? "active" : ""} href="/">{zh?"首页":"Home"}</Link>
          <Link className={pathname === "/console" ? "active" : ""} href="/console">{zh?"控制台":"Console"}</Link>
          <Link className={pathname === "/results" ? "active" : ""} href="/results">{zh?"结果":"Results"}</Link>
          <Link className={pathname === "/reproduce" ? "active" : ""} href="/reproduce">{zh?"复现":"Reproduce"}</Link>
        </nav>
        <div className="top-actions">
          <span className="status-pill"><i /> {zh?"录制证据就绪":"Recorded evidence ready"}</span>
          <button aria-label={zh ? "Switch to English" : "切换到中文"} onClick={() => setLanguage(language === "en" ? "zh" : "en")}>{language === "en" ? "中" : "EN"}</button>
        </div>
      </header>
      {children}
      <footer>
        <div className="brand compact"><span className="brand-symbol" aria-hidden="true"><i/><i/></span><span>Look Twice</span></div>
        <p>Recorded AMD GPU evidence · Simulation only · Frozen candidate artifact</p>
        <span>Apache-2.0</span>
      </footer>
    </div>
  </LanguageContext.Provider>;
}
