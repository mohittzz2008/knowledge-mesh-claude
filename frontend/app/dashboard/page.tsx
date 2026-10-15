'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Check } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import { PlatformMark } from '@/components/ui/PlatformMark';
import {
  fetchKnowledgeMesh,
  fetchNextBestAction,
  fetchPlatformRegistry,
  fetchUserProfile,
  type KnowledgeMeshResponse,
  type NextBestActionResponse,
  type PlatformRegistryItem,
  type UserProfileResponse,
} from '@/lib/api';
import { timeAgo } from '@/lib/platforms';

const STATUS_ORDER = ['weak', 'developing', 'mastered', 'insufficient'] as const;
// The backend reports "NO_EVIDENCE" for skills it has nothing on; show it with "insufficient".
const normStatus = (s: string) => {
  const lower = (s || '').toLowerCase();
  return lower === 'no_evidence' || lower === 'insufficient' ? 'insufficient' : lower;
};
const rank = (s: string) => {
  const i = STATUS_ORDER.indexOf(normStatus(s) as (typeof STATUS_ORDER)[number]);
  return i === -1 ? STATUS_ORDER.length : i;
};
const STATUS_LABEL: Record<string, string> = {
  weak: 'Needs work',
  developing: 'Developing',
  mastered: 'Strong',
  insufficient: 'Not enough evidence',
};
const STATUS_CHIP: Record<string, string> = {
  weak: 'chip-warn',
  developing: 'chip-accent',
  mastered: 'chip-ok',
  insufficient: '',
};

export default function DashboardPage() {
  const [mesh, setMesh] = useState<KnowledgeMeshResponse | null>(null);
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [next, setNext] = useState<NextBestActionResponse | null>(null);
  const [platforms, setPlatforms] = useState<PlatformRegistryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    let alive = true;
    (async () => {
      const [m, n, p, r] = await Promise.all([
        fetchKnowledgeMesh(),
        fetchNextBestAction(),
        fetchUserProfile(),
        fetchPlatformRegistry(),
      ]);
      if (!alive) return;
      setMesh(m);
      setNext(n);
      setProfile(p);
      // fetchPlatformRegistry returns {error} on failure; treat that as empty list.
      setPlatforms(Array.isArray(r) ? r : []);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const nodes = mesh?.nodes ?? [];
  const connected = platforms.filter((p) => p.connected);
  const counts = profile?.platform_counts ?? {};
  const totalEvidence = profile?.total_evidence_count ?? 0;
  const assessed = mesh?.assessed_skills_count ?? 0;
  const score =
    profile?.overall_skill_score ??
    (nodes.length ? Math.round(nodes.reduce((a, n) => a + n.data.mastery, 0) / nodes.length) : 0);

  const sourcesBySlug = new Map((profile?.skills ?? []).map((s) => [s.slug, s.sources ?? {}]));
  const visible = nodes
    .filter((n) => filter === 'all' || normStatus(n.data.status) === filter)
    .sort((a, b) => rank(a.data.status) - rank(b.data.status) || a.data.mastery - b.data.mastery);
  const statusCounts = nodes.reduce<Record<string, number>>((acc, n) => {
    const k = normStatus(n.data.status);
    acc[k] = (acc[k] ?? 0) + 1;
    return acc;
  }, {});

  const hasData = totalEvidence > 0 || assessed > 0;

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title="Dashboard"
          description="What your connected accounts say about your skills, and what to practice next."
          actions={
            <Link href="/platforms" className="btn btn-secondary btn-sm">
              Manage platforms
            </Link>
          }
        />

        {loading ? (
          <p className="text-sm text-mute">Loading…</p>
        ) : !hasData && connected.length === 0 ? (
          <section className="panel px-6 py-12 text-center">
            <h2 className="text-lg font-medium">Nothing to show yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-mute">
              Connect a platform you use (GitHub, LeetCode, Codewars, GeeksforGeeks and more). Your skills appear here
              once its public activity has been imported.
            </p>
            <Link href="/platforms" className="btn btn-primary mt-6">
              Connect a platform
            </Link>
          </section>
        ) : (
          <div className="space-y-6">
            {/* Summary strip */}
            <section className="panel grid grid-cols-2 divide-x divide-line sm:grid-cols-4">
              {[
                { k: 'Skill score', v: assessed ? `${score}` : '–', sub: assessed ? 'average mastery, out of 100' : 'no assessed skills yet' },
                { k: 'Skills assessed', v: String(assessed), sub: `of ${mesh?.total_skills ?? 0} tracked` },
                { k: 'Evidence items', v: String(totalEvidence), sub: 'imported from your accounts' },
                { k: 'Platforms', v: String(connected.length), sub: `of ${platforms.length} available` },
              ].map((s) => (
                <div key={s.k} className="px-5 py-4">
                  <p className="label">{s.k}</p>
                  <p className="tnum mt-1 text-2xl font-semibold">{s.v}</p>
                  <p className="mt-0.5 text-xs text-faint">{s.sub}</p>
                </div>
              ))}
            </section>

            <div className="grid items-start gap-6 lg:grid-cols-5">
              {/* Next step */}
              <section className="panel p-5 lg:col-span-3">
                <p className="label">Practice next</p>
                {next ? (
                  <>
                    <h2 className="mt-2 text-xl font-semibold">{next.target_skill}</h2>
                    <p className="mt-2 text-sm text-ink-2">{next.reason}</p>
                    {next.learning_objective && <p className="mt-2 text-sm text-mute">{next.learning_objective}</p>}
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <span className="chip">Suggested difficulty: {next.recommended_difficulty}</span>
                      {!next.has_sufficient_evidence && <span className="chip chip-warn">Based on little evidence</span>}
                    </div>
                    <div className="mt-5 flex gap-2">
                      <Link href="/learning-path" className="btn btn-primary btn-sm">
                        Open learning path <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                      <Link href="/code-lab" className="btn btn-secondary btn-sm">
                        Code Lab
                      </Link>
                    </div>
                  </>
                ) : (
                  <p className="mt-2 text-sm text-mute">
                    No recommendation yet. Import more activity from a connected platform to get one.
                  </p>
                )}
              </section>

              {/* Platforms */}
              <section className="panel lg:col-span-2">
                <div className="flex items-center justify-between px-5 pt-4">
                  <p className="label">Sources</p>
                  <Link href="/platforms" className="text-xs text-accent hover:underline">
                    Manage
                  </Link>
                </div>
                <ul className="mt-2 divide-y divide-line">
                  {platforms.map((p) => (
                    <li key={p.key} className="flex items-center gap-3 px-5 py-2.5">
                      <PlatformMark id={p.key} name={p.name} size={28} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-ink">{p.name}</p>
                        <p className="truncate text-xs text-faint">
                          {p.connected
                            ? `${p.connected_username} · ${timeAgo(p.last_synced_at)}`
                            : 'Not connected'}
                        </p>
                      </div>
                      {p.connected ? (
                        <span className="chip chip-ok tnum">
                          <Check className="h-3 w-3" /> {counts[p.name] ?? 0}
                        </span>
                      ) : (
                        <Link href="/platforms" className="text-xs text-accent hover:underline">
                          Connect
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
                {(profile?.codelab_artifacts_count ?? 0) > 0 && (
                  <p className="border-t border-line px-5 py-2.5 text-xs text-mute">
                    Plus {profile?.codelab_artifacts_count} Code Lab submission
                    {profile?.codelab_artifacts_count === 1 ? '' : 's'}.
                  </p>
                )}
              </section>
            </div>

            {/* Skills */}
            <section className="panel">
              <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4">
                <p className="label">Skills</p>
                <div className="flex flex-wrap gap-1" role="tablist" aria-label="Filter skills">
                  {['all', ...STATUS_ORDER.filter((s) => statusCounts[s])].map((s) => (
                    <button
                      key={s}
                      role="tab"
                      aria-selected={filter === s}
                      onClick={() => setFilter(s)}
                      className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                        filter === s ? 'bg-raised text-ink' : 'text-mute hover:text-ink'
                      }`}
                    >
                      {s === 'all' ? `All ${nodes.length}` : `${STATUS_LABEL[s]} ${statusCounts[s]}`}
                    </button>
                  ))}
                </div>
              </div>

              {visible.length === 0 ? (
                <p className="px-5 py-8 text-sm text-mute">No skills in this view yet.</p>
              ) : (
                <ul className="mt-3 divide-y divide-line">
                  {visible.map((n) => {
                    const src = Object.entries(sourcesBySlug.get(n.id) ?? sourcesBySlug.get(n.data.slug) ?? {}).filter(
                      ([, v]) => v > 0,
                    );
                    const unassessed = normStatus(n.data.status) === 'insufficient' || n.data.evidenceCount === 0;
                    return (
                      <li key={n.id} className="grid grid-cols-[1fr_auto] items-center gap-x-6 gap-y-1 px-5 py-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_auto]">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{n.data.name}</p>
                          <p className="truncate text-xs text-faint">
                            {n.data.evidenceCount} evidence item{n.data.evidenceCount === 1 ? '' : 's'}
                            {src.length > 0 && ` · ${src.map(([k, v]) => `${k} ${v}`).join(', ')}`}
                          </p>
                        </div>
                        <div className="col-span-2 order-last flex items-center gap-3 sm:order-none sm:col-span-1">
                          <div className="meter flex-1">
                            <span style={{ width: `${unassessed ? 0 : Math.min(100, Math.max(0, n.data.mastery))}%` }} />
                          </div>
                          <span className="tnum w-9 text-right text-sm text-ink-2">{unassessed ? '--' : `${Math.round(n.data.mastery)}%`}</span>
                        </div>
                        <span className={`chip justify-self-end ${STATUS_CHIP[normStatus(n.data.status)] ?? ''}`}>
                          {STATUS_LABEL[normStatus(n.data.status)] ?? n.data.status}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
              <div className="border-t border-line px-5 py-3">
                <Link href="/knowledge-mesh" className="text-sm text-accent hover:underline">
                  View as a graph
                </Link>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
