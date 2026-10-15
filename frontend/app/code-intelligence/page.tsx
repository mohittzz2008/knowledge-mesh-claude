'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { X } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import { defineMeshTheme, MESH_THEME, MONACO_FONT } from '@/components/code/monacoTheme';
import {
  analyzeGitHubFile,
  fetchCodeArtifacts,
  fetchUserProfile,
  fetchEvidenceList,
  type CodeArtifactResponse,
} from '@/lib/api';

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), {
  ssr: false,
  loading: () => <div className="flex h-full w-full items-center justify-center bg-canvas text-sm text-mute">Loading editor…</div>,
});

export default function CodeIntelligencePage() {
  const [loading, setLoading] = useState(true);
  const [connectedUsername, setConnectedUsername] = useState<string | null>(null);
  const [owner, setOwner] = useState('');
  const [repo, setRepo] = useState('');
  const [path, setPath] = useState('');
  const [userRepos, setUserRepos] = useState<string[]>([]);

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [artifactList, setArtifactList] = useState<CodeArtifactResponse[]>([]);
  const [selected, setSelected] = useState<CodeArtifactResponse | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const reqId = useRef(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [profile, artifacts] = await Promise.all([fetchUserProfile(), fetchCodeArtifacts()]);
      if (!alive) return;
      const gh = profile?.connected_platforms?.find((p) => p.platform === 'GitHub' && p.connected);
      const username = gh?.username || null;
      setConnectedUsername(username);

      if (artifacts?.items) {
        setArtifactList(artifacts.items);
        if (username && artifacts.items.length > 0) setSelected(artifacts.items[0]);
      }

      if (username) {
        setOwner(username);
        const ev = await fetchEvidenceList('GitHub');
        if (!alive) return;
        const names = new Set<string>();
        ev?.items?.forEach((item) => {
          const name = item.normalized_payload?.repository_name;
          if (name) names.add(name);
        });
        const arr = Array.from(names);
        setUserRepos(arr);
        if (arr.length > 0) setRepo(arr[0]);
      }
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const ownerMismatch =
    !!owner && !!connectedUsername && owner.trim().toLowerCase() !== connectedUsername.trim().toLowerCase();

  async function handleAnalyze(e: React.FormEvent) {
    e.preventDefault();
    if (!connectedUsername || ownerMismatch) return;
    if (!owner.trim() || !repo.trim() || !path.trim()) return;

    const id = ++reqId.current;
    setIsAnalyzing(true);
    setErrorMessage(null);
    try {
      const result = await analyzeGitHubFile(owner.trim(), repo.trim(), path.trim());
      if (id !== reqId.current) return;
      if (result) {
        setSelected(result);
        setArtifactList((prev) => [result, ...prev.filter((a) => a.id !== result.id)]);
      } else {
        setErrorMessage('The server returned no analysis for that file. Check the path and try again.');
      }
    } catch (err: unknown) {
      if (id !== reqId.current) return;
      setErrorMessage(err instanceof Error ? err.message : 'Could not fetch and analyze that file.');
    } finally {
      if (id === reqId.current) setIsAnalyzing(false);
    }
  }

  const a = selected?.analysis;
  const metrics = a
    ? [
        { k: 'Lines', v: String(a.lines_of_code) },
        { k: 'Functions', v: String(a.function_count) },
        { k: 'Classes', v: String(a.class_count ?? 0) },
        { k: 'Complexity', v: String(a.cyclomatic_complexity) },
        { k: 'Recursion', v: a.has_recursion ? 'Yes' : 'No' },
      ]
    : [];

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title="Code Intelligence"
          description="Fetch a Python file from one of your GitHub repositories and see its size, structure and complexity."
          actions={connectedUsername ? <span className="chip">GitHub: {connectedUsername}</span> : undefined}
        />

        {loading ? (
          <p className="text-sm text-mute">Loading…</p>
        ) : !connectedUsername ? (
          <section className="panel px-6 py-12 text-center">
            <h2 className="text-lg font-medium">Connect GitHub first</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-mute">
              Code Intelligence only analyzes files from repositories owned by your connected GitHub account.
            </p>
            <Link href="/platforms" className="btn btn-primary mt-6">
              Connect GitHub
            </Link>
          </section>
        ) : (
          <div className="space-y-6">
            <form onSubmit={handleAnalyze} className="panel grid gap-4 p-5 sm:grid-cols-12 sm:items-end">
              <div className="sm:col-span-3">
                <label htmlFor="ci-owner" className="label mb-1 block">Repository owner</label>
                <input id="ci-owner" className="input" value={owner} onChange={(e) => setOwner(e.target.value)} required />
              </div>
              <div className="sm:col-span-3">
                <label htmlFor="ci-repo" className="label mb-1 block">Repository</label>
                {userRepos.length > 0 ? (
                  <select id="ci-repo" className="input" value={repo} onChange={(e) => setRepo(e.target.value)} required>
                    {userRepos.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input id="ci-repo" className="input" value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="my-repository" required />
                )}
              </div>
              <div className="sm:col-span-4">
                <label htmlFor="ci-path" className="label mb-1 block">File path</label>
                <input id="ci-path" className="input font-mono" value={path} onChange={(e) => setPath(e.target.value)} placeholder="src/utils.py" required />
              </div>
              <div className="sm:col-span-2">
                <button type="submit" className="btn btn-primary w-full" disabled={isAnalyzing || ownerMismatch}>
                  {isAnalyzing ? 'Analyzing…' : 'Analyze file'}
                </button>
              </div>
              {ownerMismatch && (
                <p role="alert" className="text-sm text-warn sm:col-span-12">
                  The owner must match your connected GitHub account ({connectedUsername}).
                </p>
              )}
              {errorMessage && (
                <p role="alert" className="text-sm text-bad sm:col-span-12">
                  {errorMessage}
                </p>
              )}
            </form>

            {artifactList.length > 1 && (
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor="ci-recent" className="label">Previously analyzed</label>
                <select
                  id="ci-recent"
                  className="input w-auto max-w-full"
                  value={selected?.id ?? ''}
                  onChange={(e) => setSelected(artifactList.find((x) => x.id === e.target.value) ?? null)}
                >
                  {artifactList.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.repository}/{x.file_path}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {selected ? (
              <div className="grid gap-6 lg:grid-cols-12">
                <div className="space-y-6 lg:col-span-5">
                  <section className="panel p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="label">{selected.repository}</p>
                        <p className="mt-1 break-all font-mono text-sm">{selected.file_path}</p>
                      </div>
                      <span className="chip">{selected.language}</span>
                    </div>
                    <p className="tnum mt-3 text-xs text-mute">{selected.size_bytes} bytes</p>
                    {selected.source_url && (
                      <a href={selected.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-sm text-accent hover:underline">
                        View on GitHub
                      </a>
                    )}
                  </section>

                  {a ? (
                    <section className="panel p-5">
                      <h2 className="text-sm font-medium">Static analysis</h2>
                      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-3">
                        {metrics.map((m) => (
                          <div key={m.k}>
                            <dt className="label">{m.k}</dt>
                            <dd className="tnum mt-0.5 text-xl font-semibold">{m.v}</dd>
                          </div>
                        ))}
                      </dl>
                      {a.analysis_summary?.valid_syntax === false && (
                        <p role="alert" className="mt-4 text-sm text-warn">
                          This file has a syntax error{a.analysis_summary.error_detail ? `: ${a.analysis_summary.error_detail}` : '.'}
                        </p>
                      )}
                      {a.detected_concepts && a.detected_concepts.length > 0 && (
                        <div className="mt-5">
                          <p className="label">Concepts found</p>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {a.detected_concepts.map((c) => (
                              <span key={c} className="chip chip-accent">{c}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {a.data_structures && a.data_structures.length > 0 && (
                        <div className="mt-5">
                          <p className="label">Data structures</p>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {a.data_structures.map((d) => (
                              <span key={d} className="chip">{d}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </section>
                  ) : (
                    <p className="panel-quiet px-5 py-4 text-sm text-mute">No analysis is available for this file.</p>
                  )}
                </div>

                <section className="panel flex flex-col p-5 lg:col-span-7">
                  <div className="flex items-center justify-between gap-3">
                    <h2 className="text-sm font-medium">Source</h2>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => setIsExpanded(true)}>
                      Open in editor
                    </button>
                  </div>
                  <pre className="mt-4 max-h-[32rem] overflow-auto rounded-md border border-line bg-canvas p-4 font-mono text-xs leading-relaxed text-ink-2">
                    {selected.code_content}
                  </pre>
                </section>
              </div>
            ) : (
              <section className="panel-quiet px-6 py-12 text-center">
                <p className="text-sm text-mute">Nothing analyzed yet. Pick a repository and enter the path of a Python file above.</p>
              </section>
            )}
          </div>
        )}

        {isExpanded && selected && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/90 p-4" role="dialog" aria-modal="true" aria-label="Source viewer">
            <div className="panel flex h-[85vh] w-full max-w-5xl flex-col p-5">
              <div className="flex items-center justify-between gap-3 border-b border-line pb-3">
                <h3 className="min-w-0 truncate font-mono text-sm">
                  {selected.repository} / {selected.file_path}
                </h3>
                <button type="button" className="btn btn-quiet btn-sm" onClick={() => setIsExpanded(false)} aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-3 flex-1 overflow-hidden rounded-md border border-line bg-canvas">
                <MonacoEditor
                  height="100%"
                  defaultLanguage={selected.language.toLowerCase() === 'python' ? 'python' : 'javascript'}
                  theme={MESH_THEME}
                  beforeMount={defineMeshTheme}
                  value={selected.code_content}
                  options={{
                    readOnly: true,
                    fontSize: 13,
                    fontFamily: MONACO_FONT,
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    padding: { top: 12 },
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
