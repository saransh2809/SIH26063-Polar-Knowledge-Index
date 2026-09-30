"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { TOKEN_KEY, clientFetch } from "@/lib/api";

type Me = { username: string; display_name: string; role: "curator" | "reviewer" | "admin" };
const StaffContext = createContext<{ me: Me; logout: () => void } | null>(null);

export function useStaff() {
  const ctx = useContext(StaffContext);
  if (!ctx) throw new Error("useStaff outside StaffShell");
  return ctx;
}

function LoginForm({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username, password }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? "Login failed");
      sessionStorage.setItem(TOKEN_KEY, body.access_token);
      onLogin();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto mt-6 max-w-sm space-y-4 rounded-lg border border-border bg-card p-6">
      <h1 className="text-xl font-bold">Staff login</h1>
      <p className="text-sm text-muted-foreground">For NCPOR curators and reviewers. The public never needs to log in.</p>
      <div>
        <label htmlFor="username" className="block font-medium">Username</label>
        <input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)}
          required className="mt-1 w-full rounded border border-border px-3 py-2" />
      </div>
      <div>
        <label htmlFor="password" className="block font-medium">Password</label>
        <input id="password" type="password" autoComplete="current-password" value={password}
          onChange={(e) => setPassword(e.target.value)} required className="mt-1 w-full rounded border border-border px-3 py-2" />
      </div>
      {error && <p role="alert" className="text-bad">{error}</p>}
      <button disabled={busy} className="w-full rounded bg-accent px-4 py-2 font-medium text-on-accent disabled:opacity-60 cursor-pointer">
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export function StaffShell({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const pathname = usePathname();

  const load = useCallback(async () => {
    try {
      setMe(await clientFetch<Me>("/auth/me"));
    } catch {
      sessionStorage.removeItem(TOKEN_KEY);
      setMe(null);
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const logout = () => {
    sessionStorage.removeItem(TOKEN_KEY);
    setMe(null);
  };

  if (!checked) return <p>Loading…</p>;
  if (!me) return <LoginForm onLogin={load} />;

  const tabs = [
    { href: "/staff", label: "Overview" },
    { href: "/staff/review", label: "Review queue" },
    { href: "/staff/generate", label: "Draft new content" },
    { href: "/staff/curate", label: "Confirm links" },
    { href: "/staff/audit", label: "Audit log" },
  ];
  return (
    <StaffContext.Provider value={{ me, logout }}>
      <div className="mb-6 flex flex-wrap items-center gap-3 border-b border-border pb-3">
        <nav aria-label="Staff">
          <ul className="flex flex-wrap gap-1">
            {tabs.map((t) => {
              const active = t.href === "/staff" ? pathname === "/staff" : pathname.startsWith(t.href);
              return (
                <li key={t.href}>
                  <Link href={t.href} aria-current={active ? "page" : undefined}
                    className={`inline-block rounded px-3 py-2 ${active ? "bg-primary text-on-primary" : "hover:bg-muted"}`}>
                    {t.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <p className="ml-auto text-sm">
          Signed in as <strong>{me.display_name}</strong> ({me.role}){" "}
          <button onClick={logout} className="ml-2 text-accent underline cursor-pointer">Sign out</button>
        </p>
      </div>
      {children}
    </StaffContext.Provider>
  );
}
