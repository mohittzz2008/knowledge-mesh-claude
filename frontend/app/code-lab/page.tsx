'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import confetti from 'canvas-confetti';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import { defineMeshTheme, MESH_THEME, MONACO_FONT } from '@/components/code/monacoTheme';
import {
  fetchCodeLabProblem,
  runCodeLab,
  analyzeCodeLab,
  submitCodeLab,
  fetchCodeLabHint,
  type CodeLabProblemDetail,
  type CodeRunResponse,
  type CodeAnalyzeResponse,
  type CodeSubmitResponse,
} from '@/lib/api';

const EditorLoading = () => (
  <div className="flex h-full w-full items-center justify-center bg-canvas text-sm text-mute">Loading editor…</div>
);

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false, loading: EditorLoading });
const MonacoDiffEditor = dynamic(() => import('@monaco-editor/react').then((m) => m.DiffEditor), {
  ssr: false,
  loading: EditorLoading,
});

const PROBLEM_ID = 'problem-tree-inorder';
type Tab = 'problem' | 'hints' | 'analysis';
type Action = 'run' | 'analyze' | 'submit' | 'hint';

const TABS: { id: Tab; label: string }[] = [
  { id: 'problem', label: 'Problem' },
  { id: 'analysis', label: 'Analysis' },
  { id: 'hints', label: 'Hints' },
];

export default function CodeLabPage() {
  const [problem, setProblem] = useState<CodeLabProblemDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [suggestedCode, setSuggestedCode] = useState('');
  const [showDiff, setShowDiff] = useState(false);
  const [tab, setTab] = useState<Tab>('problem');

  const [busy, setBusy] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<CodeRunResponse | null>(null);
  const [analysis, setAnalysis] = useState<CodeAnalyzeResponse | null>(null);
  const [submitResult, setSubmitResult] = useState<CodeSubmitResponse | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [hintTotal, setHintTotal] = useState(3);

  // Each request gets an id; only the newest one may write results.
  const reqId = useRef(0);

  useEffect(() => {
    let alive = true;
    (async () => {
      const p = await fetchCodeLabProblem(PROBLEM_ID);
      if (!alive) return;
      if (p) {
        setProblem(p);
        setCode(p.initial_code);
        setSuggestedCode(p.suggested_code);
      } else {
        setLoadError('Could not load the problem. Check that the backend is running, then reload the page.');
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const problemId = problem?.id || PROBLEM_ID;
  const disabled = busy !== null || !problem;

  async function perform<T>(action: Action, call: () => Promise<T | null>, failure: string, onOk: (r: T) => void) {
    const id = ++reqId.current;
    setBusy(action);
    setError(null);
    const res = await call();
    if (id !== reqId.current) return; // a newer request superseded this one
    setBusy(null);
    if (!res) {
      setError(failure);
      return;
    }
    onOk(res);
  }

  const handleRun = () => {
    setRunResult(null);
    return perform('run', () => runCodeLab(code, 'Python', problemId), 'Could not run your code. The server did not respond; try again.', setRunResult);
  };

  const handleAnalyze = () =>
    perform('analyze', () => analyzeCodeLab(code, 'Python', problemId), 'Could not analyze your code. The server did not respond; try again.', (r) => {
      setAnalysis(r);
      setSuggestedCode(r.suggested_code);
      setTab('analysis');
    });

  const handleSubmit = () => {
    setSubmitResult(null);
    return perform('submit', () => submitCodeLab(code, 'Python', problemId), 'Could not submit your solution. Nothing was saved; try again.', (r) => {
      setSubmitResult(r);
      if (r.is_passed) confetti({ particleCount: 60, spread: 60, origin: { y: 0.6 } });
    });
  };

  const handleHint = () =>
    perform('hint', () => fetchCodeLabHint(problemId, hintLevel + 1), 'Could not load a hint. Try again.', (r) => {
      setHint(r.hint);
      setHintLevel(r.hint_level);
      setHintTotal(r.total_hints || 3);
      setTab('hints');
    });

  const hintsExhausted = hintLevel > 0 && hintLevel >= hintTotal;

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title={problem?.title ?? 'Code Lab'}
          description="Write Python in the editor, run it against the test cases, and submit when it passes. The sandbox runs Python only."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn btn-quiet btn-sm"
                aria-pressed={showDiff}
                onClick={() => setShowDiff((v) => !v)}
              >
                {showDiff ? 'Back to editor' : 'Compare with suggested solution'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleAnalyze} disabled={disabled}>
                {busy === 'analyze' ? 'Analyzing…' : 'Analyze'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={handleRun} disabled={disabled}>
                {busy === 'run' ? 'Running…' : 'Run'}
              </button>
              <button type="button" className="btn btn-primary" onClick={handleSubmit} disabled={disabled}>
                {busy === 'submit' ? 'Submitting…' : 'Submit'}
              </button>
            </div>
          }
        />

        {loadError && (
          <p role="alert" className="panel mb-4 border-bad/40 px-4 py-3 text-sm text-bad">
            {loadError}
          </p>
        )}
        {error && (
          <p role="alert" className="panel mb-4 border-bad/40 px-4 py-3 text-sm text-bad">
            {error}
          </p>
        )}

        <div className="grid gap-6 lg:grid-cols-12">
          {/* Left: problem, analysis, hints */}
          <section className="panel flex flex-col p-5 lg:col-span-4">
            <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Problem details">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={`btn btn-sm ${tab === t.id ? 'btn-secondary' : 'btn-quiet'}`}
                >
                  {t.label}
                </button>
              ))}
              {problem && (
                <span className="chip ml-auto">
                  {problem.difficulty}
                </span>
              )}
            </div>

            <div className="mt-5 space-y-5 text-sm" role="tabpanel">
              {tab === 'problem' && (
                <>
                  {!problem && !loadError && <p className="text-mute">Loading problem…</p>}
                  {problem && (
                    <>
                      <div>
                        <p className="label">Skill practiced</p>
                        <p className="mt-1 text-ink">{problem.target_skill}</p>
                        <p className="mt-2 text-ink-2">{problem.learning_objective}</p>
                      </div>
                      <p className="whitespace-pre-line text-ink-2">{problem.description}</p>
                      <div>
                        <p className="label">Test cases ({problem.test_cases.length})</p>
                        <ul className="mt-2 space-y-2">
                          {problem.test_cases.map((t, i) => (
                            <li key={i} className="panel-quiet px-3 py-2 font-mono text-xs">
                              <p className="text-mute">
                                Call: <span className="text-ink">{t.function_call}</span>
                              </p>
                              <p className="text-mute">
                                Expected: <span className="text-ink">{t.expected}</span>
                              </p>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </>
                  )}
                </>
              )}

              {tab === 'analysis' && (
                <>
                  {analysis ? (
                    <>
                      <p className={`chip ${analysis.valid_syntax ? 'chip-ok' : 'chip-bad'}`}>
                        {analysis.valid_syntax ? 'Valid Python syntax' : 'Syntax error'}
                      </p>
                      <p className="whitespace-pre-line text-ink-2">{analysis.diagnostic_report}</p>
                      <div>
                        <p className="label">About the suggested approach</p>
                        <p className="mt-1 whitespace-pre-line text-ink-2">{analysis.explanation}</p>
                      </div>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowDiff(true)}>
                        Compare with suggested solution
                      </button>
                    </>
                  ) : (
                    <>
                      <p className="text-mute">No analysis yet. Analyze reads your code and explains how it works and where it could be improved.</p>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={handleAnalyze} disabled={disabled}>
                        {busy === 'analyze' ? 'Analyzing…' : 'Analyze my code'}
                      </button>
                    </>
                  )}
                </>
              )}

              {tab === 'hints' && (
                <>
                  {hint ? (
                    <div>
                      <p className="label">
                        Hint {hintLevel} of {hintTotal}
                      </p>
                      <p className="mt-1 text-ink-2">{hint}</p>
                    </div>
                  ) : (
                    <p className="text-mute">Hints start general and get more specific. None of them give the full solution away at once.</p>
                  )}
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleHint} disabled={disabled || hintsExhausted}>
                    {busy === 'hint' ? 'Loading…' : hintsExhausted ? 'No more hints' : hintLevel > 0 ? 'Next hint' : 'Get a hint'}
                  </button>
                </>
              )}

              {submitResult && (
                <div
                  className={`panel-quiet space-y-2 px-4 py-3 ${submitResult.is_passed ? 'border-ok/40' : 'border-warn/40'}`}
                  aria-live="polite"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`chip ${submitResult.is_passed ? 'chip-ok' : 'chip-warn'}`}>
                      {submitResult.is_passed ? 'Passed' : 'Not passing yet'}
                    </span>
                    <span className="tnum text-xs text-mute">
                      {submitResult.passed_count}/{submitResult.total_tests} tests · {submitResult.execution_time_ms} ms
                    </span>
                  </div>
                  <p className="text-ink-2">{submitResult.message}</p>
                  {submitResult.evidence_id && <p className="text-xs text-mute">Saved to your evidence.</p>}
                </div>
              )}
            </div>
          </section>

          {/* Right: editor and results */}
          <div className="flex flex-col gap-4 lg:col-span-8">
            <div className="panel overflow-hidden">
              <div className="flex items-center justify-between border-b border-line px-4 py-2">
                <span className="label">{showDiff ? 'Your code vs suggested solution' : 'solution.py'}</span>
                <span className="chip">Python only</span>
              </div>
              <div className="h-[28rem] bg-canvas">
                {showDiff ? (
                  <MonacoDiffEditor
                    height="100%"
                    language="python"
                    theme={MESH_THEME}
                    beforeMount={defineMeshTheme}
                    original={code}
                    modified={suggestedCode}
                    options={{
                      fontSize: 13,
                      fontFamily: MONACO_FONT,
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      readOnly: true,
                    }}
                  />
                ) : (
                  <MonacoEditor
                    height="100%"
                    defaultLanguage="python"
                    theme={MESH_THEME}
                    beforeMount={defineMeshTheme}
                    value={code}
                    onChange={(v) => setCode(v ?? '')}
                    options={{
                      fontSize: 13,
                      fontFamily: MONACO_FONT,
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      padding: { top: 12 },
                    }}
                  />
                )}
              </div>
            </div>

            <section className="panel p-5" aria-live="polite">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium">Test results</h2>
                {runResult && (
                  <span className="tnum text-xs text-mute">
                    {runResult.passed_count}/{runResult.total_tests} passed · {runResult.execution_time_ms} ms
                  </span>
                )}
              </div>
              {busy === 'run' ? (
                <p className="mt-3 text-sm text-mute">Running your code…</p>
              ) : runResult ? (
                <div className="mt-3 space-y-3">
                  <ul className="grid gap-2 sm:grid-cols-3">
                    {runResult.test_results.map((tr) => (
                      <li key={tr.test_case} className="panel-quiet px-3 py-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-ink-2">Test {tr.test_case}</span>
                          <span className={`chip ${tr.passed ? 'chip-ok' : 'chip-bad'}`}>{tr.passed ? 'Pass' : 'Fail'}</span>
                        </div>
                        <p className="mt-2 font-mono text-mute">
                          Got: <span className="text-ink">{tr.actual}</span>
                        </p>
                        {!tr.passed && tr.error && <p className="mt-1 font-mono text-bad">{tr.error}</p>}
                      </li>
                    ))}
                  </ul>
                  {runResult.error_message && <p className="text-sm text-bad">{runResult.error_message}</p>}
                  {runResult.stdout && (
                    <pre className="panel-quiet overflow-x-auto whitespace-pre-wrap px-3 py-2 font-mono text-xs text-ink-2">{runResult.stdout}</pre>
                  )}
                  {runResult.stderr && (
                    <pre className="panel-quiet overflow-x-auto whitespace-pre-wrap border-warn/40 px-3 py-2 font-mono text-xs text-warn">
                      {runResult.stderr}
                    </pre>
                  )}
                </div>
              ) : (
                <p className="mt-3 text-sm text-mute">Run your code to see how it does on each test case.</p>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
