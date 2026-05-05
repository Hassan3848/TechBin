import React, { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { doc, onSnapshot, serverTimestamp, setDoc } from "firebase/firestore";
import { db } from "../../firebase";
import { useAuth } from "./AuthContext";

export type ThemeMode = "light" | "dark";

export type SettingsState = {
  refreshRate: string;
  sessionTimeout: string;
  theme: ThemeMode;
  notifications: boolean;
};

export const DEFAULT_SETTINGS: SettingsState = {
  refreshRate: "10",
  sessionTimeout: "30",
  theme: "light",
  notifications: true,
};

const REFRESH_OPTIONS = new Set(["5", "10", "30", "60"]);
const SESSION_OPTIONS = new Set(["15", "30", "60", "120"]);

interface SettingsContextType {
  settings: SettingsState;
  loading: boolean;
  saveSettings: (next: SettingsState) => Promise<void>;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

function safeSelect(value: unknown, allowed: Set<string>, fallback: string): string {
  const parsed = String(value ?? "");
  return allowed.has(parsed) ? parsed : fallback;
}

function normalizeSettings(data: Record<string, unknown> | undefined): SettingsState {
  if (!data) return DEFAULT_SETTINGS;
  return {
    refreshRate: safeSelect(data.refreshRate, REFRESH_OPTIONS, DEFAULT_SETTINGS.refreshRate),
    sessionTimeout: safeSelect(data.sessionTimeout, SESSION_OPTIONS, DEFAULT_SETTINGS.sessionTimeout),
    theme: data.theme === "dark" ? "dark" : "light",
    notifications: data.notifications !== false,
  };
}

export const SettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [hasDoc, setHasDoc] = useState(false);

  useEffect(() => {
    if (!user?.uid) {
      setSettings(DEFAULT_SETTINGS);
      setHasDoc(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    const ref = doc(db, "settings", user.uid);

    const unsub = onSnapshot(
      ref,
      (snap) => {
        if (!snap.exists()) {
          setSettings(DEFAULT_SETTINGS);
          setHasDoc(false);
          setLoading(false);
          return;
        }

        setSettings(normalizeSettings(snap.data() as Record<string, unknown>));
        setHasDoc(true);
        setLoading(false);
      },
      (error) => {
        console.error("settings snapshot error:", error);
        setSettings(DEFAULT_SETTINGS);
        setHasDoc(false);
        setLoading(false);
      }
    );

    return () => unsub();
  }, [user?.uid]);

  useEffect(() => {
    const root = document.documentElement;
    const dark = settings.theme === "dark";
    root.classList.toggle("dark", dark);
    root.style.colorScheme = dark ? "dark" : "light";
  }, [settings.theme]);

  const saveSettings = async (next: SettingsState) => {
    if (!user?.uid) throw new Error("You must be logged in.");

    const payload: Record<string, unknown> = {
      uid: user.uid,
      orgId: user.orgId,
      refreshRate: next.refreshRate,
      sessionTimeout: next.sessionTimeout,
      theme: next.theme,
      notifications: next.notifications,
      updatedAt: serverTimestamp(),
      updatedBy: user.email,
    };

    if (!hasDoc) {
      payload.createdAt = serverTimestamp();
      payload.createdBy = user.email;
    }

    const ref = doc(db, "settings", user.uid);
    await setDoc(ref, payload, { merge: true });
    setSettings(next);
    setHasDoc(true);
  };

  const value = useMemo<SettingsContextType>(
    () => ({
      settings,
      loading,
      saveSettings,
    }),
    [settings, loading]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
};

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) throw new Error("useSettings must be used within SettingsProvider");
  return context;
};
