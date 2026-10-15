/**
 * Frontend-only presentation data for platforms. What a platform *is* (name, status, auth type,
 * what it imports) always comes from the backend registry; this only adds a monogram and a
 * username hint so the list stays readable.
 */
export interface PlatformMeta {
  mark: string;
  kind: 'code' | 'practice';
  placeholder: string;
}

const META: Record<string, PlatformMeta> = {
  github: { mark: 'GH', kind: 'code', placeholder: 'e.g. torvalds' },
  leetcode: { mark: 'LC', kind: 'practice', placeholder: 'LeetCode username' },
  hackerrank: { mark: 'HR', kind: 'practice', placeholder: 'HackerRank username' },
  codeforces: { mark: 'CF', kind: 'practice', placeholder: 'Codeforces handle' },
  atcoder: { mark: 'AC', kind: 'practice', placeholder: 'AtCoder user id' },
  codechef: { mark: 'CC', kind: 'practice', placeholder: 'CodeChef handle' },
  codewars: { mark: 'CW', kind: 'practice', placeholder: 'Codewars username (case-sensitive)' },
  geeksforgeeks: { mark: 'GG', kind: 'practice', placeholder: 'GeeksforGeeks handle (from your profile URL)' },
  exercism: { mark: 'EX', kind: 'practice', placeholder: 'Exercism handle' },
};

export function platformMeta(key: string, name?: string): PlatformMeta {
  return (
    META[key.toLowerCase()] ?? {
      mark: (name ?? key).slice(0, 2).toUpperCase(),
      kind: 'practice',
      placeholder: 'Username',
    }
  );
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return 'never';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return 'never';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
