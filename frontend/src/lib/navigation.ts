/**
 * Where to go after signing in. Only same-app paths are accepted, so a crafted link such
 * as /login?next=https://evil.example cannot turn the sign-in page into an open redirect.
 */
export function safeNextPath(next: string | null): string {
  if (!next || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return '/'
  if (next.startsWith('/login')) return '/'
  return next
}
