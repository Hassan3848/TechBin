import React, { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  User as FirebaseUser,
} from "firebase/auth";
import { auth } from "../../firebase";

export type UserRole = "Admin" | "Viewer";

export interface User {
  uid: string;
  email: string;
  role: UserRole;
  orgId: string;
  superAdmin: boolean;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function mapClaimsToUser(claims: Record<string, unknown>, uid: string, email: string): User {
  const roleClaim = claims.role;
  const adminFlag = claims.admin === true;

  const role: UserRole =
    roleClaim === "Admin" || roleClaim === "Viewer"
      ? (roleClaim as UserRole)
      : adminFlag
      ? "Admin"
      : "Viewer";

  const orgId = typeof claims.orgId === "string" && claims.orgId.trim() ? claims.orgId : "unknown";
  const superAdmin = claims.superAdmin === true;

  return { uid, email, role, orgId, superAdmin };
}

async function toAppUser(firebaseUser: FirebaseUser, forceRefreshClaims = false): Promise<User> {
  const uid = firebaseUser.uid;
  const email = firebaseUser.email || "";
  const tokenResult = await firebaseUser.getIdTokenResult(forceRefreshClaims);
  return mapClaimsToUser(tokenResult.claims as Record<string, unknown>, uid, email);
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    const firebaseUser = auth.currentUser;
    if (!firebaseUser) return;

    setLoading(true);
    try {
      await firebaseUser.getIdToken(true);
      const appUser = await toAppUser(firebaseUser, true);
      setUser(appUser);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (firebaseUser) => {
      setLoading(true);
      try {
        if (!firebaseUser) {
          setUser(null);
          return;
        }
        const appUser = await toAppUser(firebaseUser, true);
        setUser(appUser);
      } finally {
        setLoading(false);
      }
    });

    return () => unsub();
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    setLoading(true);
    try {
      await signInWithEmailAndPassword(auth, email, password);

      const firebaseUser = auth.currentUser;
      if (firebaseUser) {
        await firebaseUser.getIdToken(true);
        const appUser = await toAppUser(firebaseUser, true);
        setUser(appUser);
      }

      return true;
    } catch (err) {
      console.error("Login failed:", err);
      setUser(null);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    setLoading(true);
    try {
      await signOut(auth);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      login,
      logout,
      refreshUser,
      isAuthenticated: !!user,
      loading,
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
