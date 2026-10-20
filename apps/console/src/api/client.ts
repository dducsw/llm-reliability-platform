// Fetch wrapper cho control-plane BFF (/api/*). Types sinh vào ./schema.d.ts bằng `pnpm gen:api`.
export async function apiGet<T>(path: string): Promise<T> {
  throw new Error(`not implemented: GET ${path}`);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  void body;
  throw new Error(`not implemented: POST ${path}`);
}
