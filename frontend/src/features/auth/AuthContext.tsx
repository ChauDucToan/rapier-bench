"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "@/lib/api";
import type { LoginRequest, RegisterRequest, UserResponse } from "@/types/api";

interface AuthContextValue {
  user: UserResponse | null;
  loading: boolean;
  error: string | null;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const current = await api.auth.me();
      setUser(current);
      setError(null);
    } catch (err) {
      setUser(null);
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    api.auth
      .me()
      .then((current) => {
        if (!ignore) {
          setUser(current);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!ignore) {
          setUser(null);
          if (err instanceof ApiError && err.status !== 401) {
            setError(err.message);
          }
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  const login = useCallback(
    async (data: LoginRequest) => {
      setError(null);
      try {
        const u = await api.auth.login(data);
        setUser(u);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Login failed";
        setError(message);
        throw err;
      }
    },
    [],
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      setError(null);
      try {
        const u = await api.auth.register(data);
        setUser(u);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Registration failed";
        setError(message);
        throw err;
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // Ignored on logout
    } finally {
      setUser(null);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        error,
        login,
        register,
        logout,
        refresh,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
