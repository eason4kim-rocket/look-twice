"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Language = "en" | "zh";
const LOCALE_STORAGE_KEY = "look-twice.locale";
const LanguageContext = createContext<{
  language: Language;
  setLanguage: (value: Language) => void;
}>({ language: "en", setLanguage: () => {} });
export const useLanguage = () => useContext(LanguageContext);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("en");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const queryLocale = new URLSearchParams(window.location.search).get("locale");
    const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    const nextLanguage =
      queryLocale === "zh" || queryLocale === "en"
        ? queryLocale
        : storedLocale === "zh" || storedLocale === "en"
          ? storedLocale
          : "en";
    setLanguage(nextLanguage);
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    window.localStorage.setItem(LOCALE_STORAGE_KEY, language);
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    const url = new URL(window.location.href);
    url.searchParams.set("locale", language);
    window.history.replaceState(window.history.state, "", url);
  }, [language, ready]);

  const changeLanguage = useCallback((value: Language) => {
    setLanguage(value);
  }, []);
  const contextValue = useMemo(
    () => ({ language, setLanguage: changeLanguage }),
    [changeLanguage, language],
  );

  return (
    <LanguageContext.Provider value={contextValue}>
      {children}
    </LanguageContext.Provider>
  );
}

export function SiteShell({ children }: { children: React.ReactNode }) {
  const { language, setLanguage } = useLanguage();
  const pathname = usePathname();
  const consoleMode = pathname === "/console";
  const zh = language === "zh";
  const localizedHref = (path: string) => `${path}?locale=${language}`;
  useEffect(() => {
    const pageTitles: Record<string, [string, string]> = {
      "/": ["Active Evidence Assurance", "主动证据保障"],
      "/console": ["Evidence Console", "证据控制台"],
      "/results": ["Frozen Results", "冻结结果"],
      "/reproduce": ["Reproduce", "复现"],
    };
    const title = pageTitles[pathname] || pageTitles["/"];
    document.title = `${zh ? title[1] : title[0]} · Look Twice`;
  }, [pathname, zh]);
  return (
    <div className={`site-shell ${consoleMode ? "shell-console" : "shell-marketing"}`}>
      <header className="topbar">
        <Link className="brand" href={localizedHref("/")}>
          <span className="brand-symbol" aria-hidden="true"><i/><i/></span>
          <span>
            Look Twice
            <small>{zh ? "主动证据保障" : "Active evidence assurance"}</small>
          </span>
        </Link>
        <nav aria-label={zh ? "主导航" : "Primary navigation"}>
          <Link className={pathname === "/" ? "active" : ""} href={localizedHref("/")}>{zh?"首页":"Home"}</Link>
          <Link className={pathname === "/console" ? "active" : ""} href={localizedHref("/console")}>{zh?"控制台":"Console"}</Link>
          <Link className={pathname === "/results" ? "active" : ""} href={localizedHref("/results")}>{zh?"结果":"Results"}</Link>
          <Link className={pathname === "/reproduce" ? "active" : ""} href={localizedHref("/reproduce")}>{zh?"复现":"Reproduce"}</Link>
        </nav>
        <div className="top-actions">
          <span className="status-pill"><i /> {zh?"录制证据就绪":"Recorded evidence ready"}</span>
          <button
            type="button"
            lang={zh ? "en" : "zh-CN"}
            aria-label={zh ? "切换到英文" : "Switch to Chinese"}
            title={zh ? "Switch to English" : "切换到中文"}
            onClick={() => setLanguage(language === "en" ? "zh" : "en")}
          >
            {language === "en" ? "中文" : "EN"}
          </button>
        </div>
      </header>
      {children}
      <footer>
        <div className="brand compact"><span className="brand-symbol" aria-hidden="true"><i/><i/></span><span>Look Twice</span></div>
        <p>{zh
          ? "录制的 AMD GPU 证据 · 仅限仿真 · 冻结候选产物"
          : "Recorded AMD GPU evidence · Simulation only · Frozen candidate artifact"}</p>
        <span>Apache-2.0</span>
      </footer>
    </div>
  );
}
