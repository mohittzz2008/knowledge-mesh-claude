/** Static illustration of a skill graph. Sample data, labelled as such on the page. */
const NODES = [
  { id: 'arrays', label: 'Arrays', x: 70, y: 70, m: 0.9 },
  { id: 'strings', label: 'Strings', x: 70, y: 190, m: 0.8 },
  { id: 'hash', label: 'Hash maps', x: 210, y: 130, m: 0.7 },
  { id: 'rec', label: 'Recursion', x: 350, y: 70, m: 0.45 },
  { id: 'trees', label: 'Trees', x: 350, y: 190, m: 0.35 },
  { id: 'graphs', label: 'Graphs', x: 490, y: 130, m: 0.15 },
];
const EDGES: Array<[string, string]> = [
  ['arrays', 'hash'],
  ['strings', 'hash'],
  ['hash', 'rec'],
  ['hash', 'trees'],
  ['rec', 'trees'],
  ['trees', 'graphs'],
  ['rec', 'graphs'],
];

export function SkillGraph() {
  const by = Object.fromEntries(NODES.map((n) => [n.id, n]));
  return (
    <svg viewBox="0 0 560 260" role="img" aria-label="Example skill graph: arrays and strings lead to hash maps, recursion and trees, then graphs" className="h-auto w-full">
      {EDGES.map(([a, b]) => (
        <line key={a + b} x1={by[a].x} y1={by[a].y} x2={by[b].x} y2={by[b].y} stroke="var(--color-line-strong)" strokeWidth="1.2" />
      ))}
      {NODES.map((n) => {
        const color = n.m >= 0.65 ? 'var(--color-ok)' : n.m >= 0.3 ? 'var(--color-accent)' : 'var(--color-warn)';
        const r = 20;
        const c = 2 * Math.PI * (r - 3);
        return (
          <g key={n.id}>
            <circle cx={n.x} cy={n.y} r={r} fill="var(--color-surface)" stroke="var(--color-line-strong)" />
            <circle
              cx={n.x}
              cy={n.y}
              r={r - 3}
              fill="none"
              stroke={color}
              strokeWidth="3"
              strokeDasharray={`${c * n.m} ${c}`}
              transform={`rotate(-90 ${n.x} ${n.y})`}
              strokeLinecap="round"
            />
            <text x={n.x} y={n.y + 4} textAnchor="middle" fontSize="10" fill="var(--color-ink)" fontFamily="var(--font-mono)">
              {Math.round(n.m * 100)}
            </text>
            <text x={n.x} y={n.y + 38} textAnchor="middle" fontSize="12" fill="var(--color-ink-2)">
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
