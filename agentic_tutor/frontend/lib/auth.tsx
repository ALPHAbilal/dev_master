"use client";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Identity } from "./api/types";
const Auth = createContext<Identity | null>(null);
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState<SupabaseClient | null>(() => {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL,
      key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    return url && key ? createClient(url, key) : null;
  });
  const [user, setUser] = useState<string | null>(client ? null : "stub-user");
  useEffect(() => {
    if (!client) return;
    let active = true;
    void client.auth
      .getSession()
      .then(({ data }) => {
        if (active) setUser(data.session?.user.id ?? null);
      })
      .catch(() => {
        if (active) setUser(null);
      });
    const { data } = client.auth.onAuthStateChange((_event, session) =>
      setUser(session?.user.id ?? null),
    );
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [client]);
  const value = useMemo<Identity>(
    () => ({
      user_id: user,
      getToken: async () =>
        client
          ? ((await client.auth.getSession()).data.session?.access_token ??
            null)
          : "stub-token",
    }),
    [client, user],
  );
  return <Auth.Provider value={value}>{children}</Auth.Provider>;
}
export function useAuth() {
  const value = useContext(Auth);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
