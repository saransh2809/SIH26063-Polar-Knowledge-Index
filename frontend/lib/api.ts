// Server components call the backend directly; the browser goes through the /api rewrite.
const SERVER_BASE = process.env.BACKEND_URL ?? "http://127.0.0.1:8010";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

/** For server components. Never cached: the archive and review states change. */
export async function serverGet<T>(path: string): Promise<T> {
  return parse<T>(await fetch(`${SERVER_BASE}${path}`, { cache: "no-store" }));
}

export const TOKEN_KEY = "ncpor-staff-token";

/** For client components. Adds the staff token when one is stored. */
export async function clientFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = typeof window !== "undefined" ? window.sessionStorage.getItem(TOKEN_KEY) : null;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return parse<T>(await fetch(`/api${path}`, { ...init, headers }));
}

/** Page images are served by the backend; route them through the rewrite. */
export function apiUrl(path: string | null | undefined): string | undefined {
  return path ? `/api${path}` : undefined;
}
