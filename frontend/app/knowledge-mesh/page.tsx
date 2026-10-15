'use client';

import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ExternalLink, X } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import { fetchKnowledgeMesh, type KnowledgeMeshNodeData } from '@/lib/api';

type StatusStyle = { label: string; text: string; bar: string; dot: string };

function isUnassessed(status: string, evidenceCount?: number): boolean {
  const norm = (status || '').toLowerCase();
  return norm === 'no_evidence' || norm === 'insufficient' || (evidenceCount !== undefined && evidenceCount === 0);
}

function statusStyle(status: string): StatusStyle {
  const norm = (status || '').toLowerCase();
  switch (norm) {
    case 'mastered':
      return { label: 'Mastered', text: 'text-ok', bar: 'bg-ok', dot: 'bg-ok' };
    case 'developing':
      return { label: 'Developing', text: 'text-accent', bar: 'bg-accent', dot: 'bg-accent' };
    case 'weak':
      return { label: 'Needs work', text: 'text-warn', bar: 'bg-warn', dot: 'bg-warn' };
    case 'no_evidence':
    case 'insufficient':
    default:
      return { label: 'Not enough data', text: 'text-faint', bar: 'bg-faint', dot: 'bg-faint' };
  }
}

const LEGEND: Array<{ status: string; range: string }> = [
  { status: 'mastered', range: '80% and up' },
  { status: 'developing', range: '60-79%' },
  { status: 'weak', range: 'below 60%' },
  { status: 'NO_EVIDENCE', range: 'no evidence yet' },
];

const SkillNode = memo(function SkillNode({ data, selected }: { data: KnowledgeMeshNodeData; selected?: boolean }) {
  const st = statusStyle(data.status);
  const unassessed = isUnassessed(data.status, data.evidenceCount);
  return (
    <div
      className={`w-44 rounded-lg border bg-surface px-3 py-2.5 ${
        selected ? 'border-accent' : 'border-line-strong hover:border-mute'
      }`}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-line-strong !bg-faint" />
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-ink">{data.name}</span>
        <span className={`tnum shrink-0 text-xs ${st.text}`}>{unassessed ? '--' : `${data.mastery}%`}</span>
      </div>
      <div className="meter mt-2">
        <span className={st.bar} style={{ width: `${unassessed ? 0 : Math.max(data.mastery, 3)}%` }} />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-mute">
        <span className={st.text}>{st.label}</span>
        <span className="tnum">{data.evidenceCount} items</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-line-strong !bg-faint" />
    </div>
  );
});

export default function KnowledgeMeshPage() {
  const nodeTypes = useMemo(() => ({ skillNode: SkillNode }), []);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selected, setSelected] = useState<KnowledgeMeshNodeData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIsLoading(true);
      setLoadFailed(false);
      const res = await fetchKnowledgeMesh();
      if (cancelled) return;
      if (!res || !res.nodes) {
        setLoadFailed(true);
        setIsLoading(false);
        return;
      }
      setNodes(
        res.nodes.map(n => ({
          id: n.id,
          type: n.type || 'skillNode',
          position: n.position,
          data: n.data as unknown as Record<string, unknown>,
        }))
      );
      setEdges(
        (res.edges ?? []).map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
          style: { stroke: 'var(--color-line-strong)', strokeWidth: 1.5 },
        }))
      );
      const withEvidence = res.nodes.find(n => n.data.evidenceCount > 0);
      setSelected(withEvidence ? withEvidence.data : res.nodes[0]?.data ?? null);
      setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [setNodes, setEdges, reloadKey]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelected(node.data as unknown as KnowledgeMeshNodeData);
  }, []);

  const isEmpty = !isLoading && !loadFailed && nodes.length === 0;
  const sel = selected ? statusStyle(selected.status) : null;

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title="Skill graph"
          description="Each skill is scored from the code and exercises you have imported. Select a skill to see what the score is based on."
          actions={
            <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2" aria-label="Legend">
              {LEGEND.map(l => (
                <li key={l.status} className="flex items-center gap-1.5">
                  <span className={`h-2.5 w-2.5 rounded-full ${statusStyle(l.status).dot}`} aria-hidden />
                  {statusStyle(l.status).label}
                  <span className="text-xs text-faint">{l.range}</span>
                </li>
              ))}
            </ul>
          }
        />

        {isLoading ? (
          <div className="panel flex h-[60vh] items-center justify-center text-sm text-mute" role="status">
            Loading your skill graph…
          </div>
        ) : loadFailed ? (
          <div className="panel flex h-[40vh] flex-col items-center justify-center gap-3 px-6 text-center" role="alert">
            <p className="text-sm text-ink-2">The skill graph could not be loaded. Check that the backend is running.</p>
            <button type="button" className="btn btn-secondary" onClick={() => setReloadKey(k => k + 1)}>
              Try again
            </button>
          </div>
        ) : isEmpty ? (
          <div className="panel flex h-[40vh] flex-col items-center justify-center gap-3 px-6 text-center">
            <h2 className="text-base font-semibold">No skills to show yet</h2>
            <p className="max-w-md text-sm text-mute">
              The graph is built from your imported work. Connect a platform and run a sync to see your skills here.
            </p>
            <Link href="/platforms" className="btn btn-primary">
              Go to platforms
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <div className="panel h-[60vh] min-h-[420px] overflow-hidden">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                colorMode="dark"
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background color="var(--color-line)" gap={28} size={1} />
                <Controls showInteractive={false} />
              </ReactFlow>
            </div>

            <aside className="panel p-5" aria-label="Selected skill">
              {selected && sel ? (
                <div className="space-y-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="label">{selected.category}</p>
                      <h2 className="text-lg font-semibold">{selected.name}</h2>
                    </div>
                    <button type="button" onClick={() => setSelected(null)} className="btn btn-quiet btn-sm" aria-label="Close skill details">
                      <X className="h-4 w-4" aria-hidden />
                    </button>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-baseline justify-between text-sm">
                      <span className={sel.text}>{sel.label}</span>
                      <span className="tnum text-ink">
                        {isUnassessed(selected.status, selected.evidenceCount) ? '--' : `${selected.mastery}%`}
                      </span>
                    </div>
                    <div className="meter">
                      <span
                        className={sel.bar}
                        style={{
                          width: `${isUnassessed(selected.status, selected.evidenceCount) ? 0 : Math.max(selected.mastery, 3)}%`,
                        }}
                      />
                    </div>
                    <p className="text-sm text-mute">
                      Evidence: {selected.evidenceStrength.toLowerCase()} ({selected.evidenceCount} {selected.evidenceCount === 1 ? 'item' : 'items'})
                    </p>
                  </div>

                  <section>
                    <h3 className="label mb-1.5">Where this comes from</h3>
                    {selected.sources && selected.sources.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {selected.sources.map(s => (
                          <span key={s} className="chip">{s}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-mute">No imported source is linked to this skill yet.</p>
                    )}
                  </section>

                  {selected.explanation && (
                    <section>
                      <h3 className="label mb-1.5">Why this score</h3>
                      <p className="text-sm leading-relaxed text-ink-2">{selected.explanation}</p>
                    </section>
                  )}

                  <section>
                    <h3 className="label mb-1.5">Linked files ({selected.linkedArtifacts?.length ?? 0})</h3>
                    {selected.linkedArtifacts && selected.linkedArtifacts.length > 0 ? (
                      <ul className="max-h-48 space-y-2 overflow-y-auto">
                        {selected.linkedArtifacts.map(art => (
                          <li key={art.id} className="rounded-md border border-line px-3 py-2 text-sm">
                            <div className="flex items-center justify-between gap-2">
                              <span className="truncate font-medium">{art.repository}</span>
                              <span className="shrink-0 text-xs text-mute">{art.language}</span>
                            </div>
                            <p className="truncate font-mono text-xs text-mute">{art.file_path}</p>
                            <div className="mt-1 flex items-center justify-between text-xs">
                              <span className="tnum text-faint">{art.lines_of_code} lines</span>
                              <Link href="/code-intelligence" className="inline-flex items-center gap-1 text-accent hover:underline">
                                Inspect <ExternalLink className="h-3 w-3" aria-hidden />
                              </Link>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-mute">
                        No files are linked to this skill yet.{' '}
                        <Link href="/code-intelligence" className="text-accent hover:underline">Analyze a file</Link>
                      </p>
                    )}
                  </section>

                  <div className="flex flex-col gap-2 border-t border-line pt-4">
                    <Link href="/code-lab" className="btn btn-primary">Practice in Code Lab</Link>
                    <Link href="/platforms" className="btn btn-quiet">Sync more data</Link>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-mute">Select a skill in the graph to see its score and sources.</p>
              )}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
