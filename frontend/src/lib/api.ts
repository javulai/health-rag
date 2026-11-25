export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'thesis-ui' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(120000),
  });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, typeof value.detail === 'string' ? value.detail : 'Хүсэлтийг гүйцэтгэж чадсангүй. Дахин оролдоно уу.');
  return value as T;
}
