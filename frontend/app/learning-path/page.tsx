'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Check, ExternalLink, Lock } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import {
  fetchLearningPath,
  fetchPracticeRecommendations,
  type LearningPathResponse,
  type LearningPathStep,
  type PracticeRecommendation,
} from '@/lib/api';

const STATUS: Record<LearningPathStep['status'], { label: string; chip: string }> = {
  completed: { label: 'Strong', chip: 'chip-ok' },
  in_progress: { label: 'Current focus', chip: 'chip-warn' },
  recommended: { label: 'Up next', chip: 'chip-accent' },
  locked: { label: 'Locked', chip: '' },
};

export default function LearningPathPage() {
  const [path, setPath] = useState<LearningPathResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<LearningPathStep | null>(null);
  const [recs, setRecs] = useState<PracticeRecommendation[]>([]);
  const [recsLoading, setRecsLoading] = useState(false);
  const requestId = useRef(0);

  // Latest-wins: a slow response for a previously selected step must not overwrite a newer one.
  const loadRecs = useCallback(async (slug: string) => {
    const id = ++requestId.current;
    setRecsLoading(true);
    const res = await fetchPracticeRecommendations(slug);
    if (id !== requestId.current) return;
    setRecs(res?.recommendations ?? []);
    setRecsLoading(false);
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      const res = await fetchLearningPath();
      if (!alive) return;
      if (!res) {
        setFailed(true);
      } else {
        setPath(res);
        const first = res.steps.find((s) => s.status === 'in_progress') ?? res.steps.find((s) => s.status !== 'locked');
        if (first) {
          setSelected(first);
          void loadRecs(first.slug);
        }
      }
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, [loadRecs]);

  const steps = path?.steps ?? [];
  const done = steps.filter((s) => s.status === 'completed').length;

  function select(step: LearningPathStep) {
    if (step.status === 'locked') return;
    setSelected(step);
    void loadRecs(step.slug);
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title="Learning path"
          description="Skills in the order their prerequisites suggest, with practice problems for the one you pick."
          actions={
            <Link href="/knowledge-mesh" className="btn btn-secondary btn-sm">
              Open skill graph
            </Link>
          }
        />

        {loading && <p className="text-sm text-mute">Loading…</p>}

        {failed && !loading && (
          <p role="alert" className="panel p-4 text-sm text-ink-2">
            Couldn&apos;t load your learning path. Check that the backend is running and you are signed in.
          </p>
        )}

        {!loading && !failed && steps.length === 0 && (
          <div className="panel px-6 py-12 text-center">
            <h2 className="text-lg font-medium">No path yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-mute">
              A path is built from your imported activity. Connect a platform first.
            </p>
            <Link href="/platforms" className="btn btn-primary mt-6">
              Connect a platform
            </Link>
          </div>
        )}

        {steps.length > 0 && (
          <div className="grid items-start gap-6 lg:grid-cols-5">
            <section className="panel lg:col-span-3" aria-label="Skills in order">
              <div className="border-b border-line px-5 py-4">
                <div className="flex items-baseline justify-between text-sm">
                  <span className="text-ink-2">
                    Goal: <span className="text-ink">{path?.target_goal}</span>
                  </span>
                  <span className="tnum text-mute">
                    {done} of {steps.length} strong
                  </span>
                </div>
                <div className="meter mt-3">
                  <span style={{ width: `${(done / steps.length) * 100}%` }} />
                </div>
              </div>
              <ol className="divide-y divide-line">
                {steps.map((s) => {
                  const locked = s.status === 'locked';
                  const active = selected?.id === s.id;
                  return (
                    <li key={s.id}>
                      <button
                        type="button"
                        onClick={() => select(s)}
                        disabled={locked}
                        aria-current={active ? 'true' : undefined}
                        className={`flex w-full items-start gap-4 px-5 py-4 text-left transition-colors ${
                          active ? 'bg-raised' : 'hover:bg-raised/50'
                        } ${locked ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                      >
                        <span className="tnum mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-line-strong text-xs text-mute">
                          {s.status === 'completed' ? <Check className="h-3.5 w-3.5 text-ok" aria-hidden /> : locked ? <Lock className="h-3 w-3" aria-hidden /> : s.step_number}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="text-[15px] font-medium">{s.title}</span>
                            <span className={`chip ${STATUS[s.status].chip}`}>{STATUS[s.status].label}</span>
                          </span>
                          <span className="mt-1 block text-[13px] text-mute">
                            {locked ? `Needs: ${s.prerequisites.join(', ') || 'earlier skills'}` : s.why}
                          </span>
                          {!locked && (
                            <span className="mt-2 flex items-center gap-3">
                              <span className="meter w-40">
                                <span style={{ width: `${s.evidence_count === 0 ? 0 : Math.min(100, s.mastery)}%` }} />
                              </span>
                              <span className="tnum text-xs text-faint">
                                {s.evidence_count === 0 ? '--' : `${Math.round(s.mastery)}%`} · {s.evidence_count} item{s.evidence_count === 1 ? '' : 's'}
                              </span>
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </section>

            <aside className="panel p-5 lg:sticky lg:top-20 lg:col-span-2" aria-label="Practice for the selected skill">
              {selected ? (
                <>
                  <p className="label">Practice</p>
                  <h2 className="mt-1 text-lg font-semibold">{selected.title}</h2>
                  <Link href="/code-lab" className="btn btn-secondary btn-sm mt-3">
                    Try it in Code Lab <ArrowRight className="h-3.5 w-3.5" />
                  </Link>

                  <h3 className="label mt-6">Problems to solve</h3>
                  {recsLoading ? (
                    <p className="mt-2 text-sm text-mute">Loading…</p>
                  ) : recs.length === 0 ? (
                    <p className="mt-2 text-sm text-mute">
                      No problems found for this skill on your connected platforms. Code Lab has exercises for it.
                    </p>
                  ) : (
                    <ul className="mt-2 divide-y divide-line">
                      {recs.map((r) => {
                        const target = r.target_difficulty;
                        const mismatch = target && target.toLowerCase() !== r.difficulty.toLowerCase();
                        return (
                          <li key={r.problem_id} className="py-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-ink">{r.title}</p>
                                <p className="mt-0.5 text-xs text-faint">
                                  {r.platform} · {r.difficulty}
                                  {mismatch ? ` (aimed for ${target})` : ''}
                                </p>
                              </div>
                              {r.url && (
                                <a href={r.url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm shrink-0" aria-label={`Open ${r.title}`}>
                                  Open <ExternalLink className="h-3 w-3" />
                                </a>
                              )}
                            </div>
                            <p className="mt-1.5 text-[13px] text-mute">{r.reason}</p>
                            {!r.is_real_data && <span className="chip chip-warn mt-2">{r.status_label}</span>}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </>
              ) : (
                <p className="text-sm text-mute">Select a skill to see practice problems.</p>
              )}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
