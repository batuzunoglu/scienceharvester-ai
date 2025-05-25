// frontend/utils/userId.ts
let cached: string | null = null;

export function getUserId(): string {
  if (cached) return cached;
  const existing = localStorage.getItem('uid');
  if (existing) {
    cached = existing;
  } else {
    cached = crypto.randomUUID();
    localStorage.setItem('uid', cached);
  }
  return cached;
}