import { createContext, useContext, useMemo, useState } from "react";
import apiClient from "../api/client";

const AuthContext = createContext(null);

/**
 * Read the stored user object from localStorage safely.
 */
function readStoredUser() {
  const rawUser = localStorage.getItem("auth_user");
  if (!rawUser) {
    return null;
  }
  try {
    return JSON.parse(rawUser);
  } catch (error) {
    localStorage.removeItem("auth_user");
    return null;
  }
}

/**
 * Provide authentication state and actions to descendant components.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);

  /**
   * Authenticate a user, persist token state, and return API response data.
   */
  async function login(credentials) {
    const response = await apiClient.post("/api/auth/login", credentials);
    const authData = response?.data?.data ?? {};
    localStorage.setItem("access_token", authData?.access_token ?? "");
    localStorage.setItem("auth_user", JSON.stringify(authData?.user ?? null));
    setUser(authData?.user ?? null);
    return authData;
  }

  /**
   * Register a new user and persist returned auth state.
   */
  async function register(payload) {
    const response = await apiClient.post("/api/auth/register", payload);
    const authData = response?.data?.data ?? {};
    localStorage.setItem("access_token", authData?.access_token ?? "");
    localStorage.setItem("auth_user", JSON.stringify(authData?.user ?? null));
    setUser(authData?.user ?? null);
    return authData;
  }

  /**
   * Clear local authentication state.
   */
  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_user");
    setUser(null);
  }

  const value = useMemo(
    function buildAuthContextValue() {
      return {
        user,
        login,
        register,
        logout,
        isAuthenticated: Boolean(user && localStorage.getItem("access_token"))
      };
    },
    [user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Return the active authentication context.
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
