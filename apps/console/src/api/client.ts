// Fetch wrapper cho control-plane BFF (/api/*). Types sinh vào ./schema.d.ts bằng `pnpm gen:api`.
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

const TOKEN_KEY = "reflex.console.token";

function authHeaders(): Record<string, string> {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY) ?? import.meta.env.VITE_CONSOLE_TOKEN;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: {
      ...authHeaders(),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((j: { detail?: string }) => j.detail)
      .catch(() => undefined);
    throw new ApiError(res.status, detail ?? res.statusText);
  }
  return (await res.json()) as T;
}

export const apiGet = <T>(path: string): Promise<T> => request<T>("GET", path);
export const apiPost = <T>(path: string, body?: unknown): Promise<T> => request<T>("POST", path, body ?? {});

export function setConsoleToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // sessionStorage bị chặn: bỏ qua, dùng VITE_CONSOLE_TOKEN
  }
}
