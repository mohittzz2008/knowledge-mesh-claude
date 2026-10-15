'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, Check, ChevronDown, ExternalLink, Loader2 } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import { PlatformMark } from '@/components/ui/PlatformMark';
import {
  disconnectPlatformUser,
  fetchPlatformRegistry,
  syncPlatformUser,
  validatePlatformUser,
  type PlatformRegistryItem,
  type PlatformSyncResponse,
} from '@/lib/api';
import { platformMeta, timeAgo } from '@/lib/platforms';

type Stage = 'idle' | 'verifying' | 'importing' | 'done' | 'error';

function statusNote(p: PlatformRegistryItem): string | null {
  switch (p.status) {
    case 'LIMITED':
      return 'Limited: this site has no official API, so the import reads the public profile page and may break if the site changes.';
    case 'OAUTH_REQUIRED':
      return 'Needs an account token.';
    case 'PLANNED':
    case 'UNSUPPORTED':
      return 'Not available yet.';
    default:
      return null;
  }
}

export default function PlatformsPage() {
  const [platforms, setPlatforms] = useState<PlatformRegistryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  const [openKey, setOpenKey] = useState<string | null>(null);
  const [username, setUsername] = useState('');
  const [token, setToken] = useState('');
  const [stage, setStage] = useState<Stage>('idle');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PlatformSyncResponse | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await fetchPlatformRegistry();
    if (Array.isArray(data)) {
      setPlatforms(data);
      setLoadFailed(false);
      setLoadError(null);
    } else {
      setLoadFailed(true);
      setLoadError((data as { error: string }).error ?? 'Unknown error');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    let alive = true;
    fetchPlatformRegistry().then((data) => {
      if (!alive) return;
      if (Array.isArray(data)) {
        setPlatforms(data);
        setLoadFailed(false);
        setLoadError(null);
      } else {
        setLoadFailed(true);
        setLoadError((data as { error: string }).error ?? 'Unknown error');
      }
      setLoading(false);
    });
    return () => {
      alive = false;
    };
  }, []);

  const working = stage === 'verifying' || stage === 'importing';

  function toggle(p: PlatformRegistryItem) {
    if (working) return;
    if (openKey === p.key) {
      setOpenKey(null);
      return;
    }
    setOpenKey(p.key);
    setUsername(p.connected_username ?? '');
    setToken('');
    setStage('idle');
    setError(null);
    setResult(null);
    setConfirmDisconnect(null);
  }

  async function run(p: PlatformRegistryItem) {
    const handle = username.trim();
    const needsToken = p.auth_type === 'api_key';
    if (!handle) return setError('Enter a username first.');
    if (needsToken && !token.trim()) return setError('This platform needs an API key.');

    setError(null);
    setResult(null);
    try {
      if (!needsToken) {
        setStage('verifying');
        const check = await validatePlatformUser(p.key, handle);
        if (!check) throw new Error('Could not reach the Knowledge Mesh server. Is the backend running?');
        if (!check.valid) throw new Error(check.detail || `No ${p.name} account found for "${handle}".`);
      }
      setStage('importing');
      const res = await syncPlatformUser(p.key, handle, p.auth_type, needsToken ? token.trim() : undefined);
      if (!res) throw new Error('The server returned an empty response.');
      setResult(res);
      setStage('done');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed.');
      setStage('error');
    }
  }

  async function disconnect(key: string) {
    setBusyKey(key);
    try {
      await disconnectPlatformUser(key);
      setConfirmDisconnect(null);
      if (openKey === key) setOpenKey(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not disconnect.');
    } finally {
      setBusyKey(null);
    }
  }

  const connectedCount = platforms.filter((p) => p.connected).length;

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title="Platforms"
          description="Connect the accounts you practice and build on. Only public data is read, using the username you give. Everything you connect feeds the same skill map."
          actions={
            !loading && !loadFailed ? (
              <span className="text-sm text-mute tnum">
                {connectedCount} of {platforms.length} connected
              </span>
            ) : undefined
          }
        />

        {loading && (
          <div className="flex items-center gap-2 text-sm text-mute">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading platforms…
          </div>
        )}

        {loadFailed && !loading && (
          <div className="panel flex items-start gap-3 p-4 text-sm">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
            <div>
              <p className="text-ink">Couldn&apos;t load the platform list.</p>
              {loadError && (
                <p className="mt-1 font-mono text-xs text-bad">{loadError}</p>
              )}
              <p className="mt-1 text-mute">
                Make sure the backend is running at{' '}
                <code className="text-xs">{process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000'}</code>, then{' '}
                <button className="text-accent underline underline-offset-2" onClick={() => { setLoading(true); load(); }}>
                  try again
                </button>
                .
              </p>
            </div>
          </div>
        )}

        <ul className="panel divide-y divide-line overflow-hidden">
          {platforms.map((p) => {
            const meta = platformMeta(p.key, p.name);
            const isOpen = openKey === p.key;
            const note = statusNote(p);
            const unavailable = p.status === 'PLANNED' || p.status === 'UNSUPPORTED';
            return (
              <li key={p.key}>
                <div className="flex items-center gap-4 px-4 py-3.5 sm:px-5">
                  <PlatformMark id={p.key} name={p.name} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                      <h2 className="text-[15px] font-medium text-ink">{p.name}</h2>
                      {p.connected ? (
                        <span className="chip chip-ok">
                          <Check className="h-3 w-3" /> {p.connected_username}
                        </span>
                      ) : p.status === 'LIMITED' ? (
                        <span className="chip chip-warn">Limited</span>
                      ) : null}
                      <span className="text-xs text-faint">{meta.kind === 'code' ? 'Source code' : 'Problem solving'}</span>
                    </div>
                    <p className="mt-0.5 truncate text-[13px] text-mute" title={p.data_scope_description}>
                      {p.connected && p.last_synced_at ? `Synced ${timeAgo(p.last_synced_at)} · ` : ''}
                      {p.data_scope_description}
                    </p>
                  </div>
                  <button
                    onClick={() => toggle(p)}
                    disabled={unavailable || (working && !isOpen)}
                    aria-expanded={isOpen}
                    className={`btn btn-sm ${p.connected ? 'btn-secondary' : 'btn-primary'}`}
                  >
                    {p.connected ? 'Manage' : 'Connect'}
                    <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                  </button>
                </div>

                {isOpen && (
                  <div className="border-t border-line bg-canvas/50 px-4 py-5 sm:px-5 sm:pl-[76px]">
                    {note && <p className="mb-4 max-w-xl text-[13px] text-warn">{note}</p>}

                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        run(p);
                      }}
                      className="max-w-xl space-y-4"
                    >
                      <div>
                        <label htmlFor={`u-${p.key}`} className="label mb-1.5 block">
                          {p.name} username
                        </label>
                        <input
                          id={`u-${p.key}`}
                          className="input"
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          placeholder={meta.placeholder}
                          autoComplete="off"
                          autoCapitalize="off"
                          spellCheck={false}
                          disabled={working}
                        />
                      </div>

                      {p.auth_type === 'api_key' && (
                        <div>
                          <label htmlFor={`t-${p.key}`} className="label mb-1.5 block">
                            API key
                          </label>
                          <input
                            id={`t-${p.key}`}
                            type="password"
                            className="input"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            placeholder="Paste your key"
                            autoComplete="off"
                            disabled={working}
                          />
                          <p className="mt-1.5 text-xs text-faint">
                            Sent to the server only to fetch your progress from {p.name}.
                          </p>
                        </div>
                      )}

                      <div className="flex flex-wrap items-center gap-3">
                        <button type="submit" className="btn btn-primary" disabled={working}>
                          {working && <Loader2 className="h-4 w-4 animate-spin" />}
                          {stage === 'verifying'
                            ? 'Checking profile…'
                            : stage === 'importing'
                              ? 'Importing…'
                              : p.connected
                                ? 'Sync now'
                                : 'Connect and import'}
                        </button>
                        {p.documentation_url && (
                          <a
                            href={p.documentation_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[13px] text-mute hover:text-ink"
                          >
                            {p.name} <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    </form>

                    {error && (
                      <div role="alert" className="mt-4 flex max-w-xl items-start gap-2.5 rounded-md border border-bad/30 bg-bad/10 px-3 py-2.5 text-[13px] text-ink-2">
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-bad" />
                        <span>{error}</span>
                      </div>
                    )}

                    {result && stage === 'done' && (
                      <div className="mt-4 max-w-xl rounded-md border border-ok/30 bg-ok/10 px-4 py-3.5 text-[13px]">
                        <p className="font-medium text-ink">
                          <Check className="mr-1.5 inline h-4 w-4 text-ok" />
                          {result.synced_evidence_count > 0
                            ? `Imported ${result.synced_evidence_count} new item${result.synced_evidence_count === 1 ? '' : 's'}`
                            : 'Connected, nothing new to import'}
                          {result.updated_evidence_count ? `, refreshed ${result.updated_evidence_count}` : ''}
                        </p>
                        <p className="mt-1 text-mute">{result.message}</p>
                        {!!result.profile_summary?.highlights?.length && (
                          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
                            {result.profile_summary.highlights.map((h) => (
                              <div key={h.label}>
                                <dt className="text-xs text-faint">{h.label}</dt>
                                <dd className="tnum text-ink">{String(h.value)}</dd>
                              </div>
                            ))}
                          </dl>
                        )}
                        <Link href="/dashboard" className="mt-3 inline-block text-accent underline-offset-2 hover:underline">
                          See it on your dashboard
                        </Link>
                      </div>
                    )}

                    {p.connected && (
                      <div className="mt-5 max-w-xl border-t border-line pt-4">
                        {confirmDisconnect === p.key ? (
                          <div className="flex flex-wrap items-center gap-3 text-[13px]">
                            <span className="text-ink-2">Stop using {p.name} in your skill map? Imported data is kept and used again if you reconnect.</span>
                            <button className="btn btn-danger btn-sm" onClick={() => disconnect(p.key)} disabled={busyKey === p.key}>
                              {busyKey === p.key && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Yes, disconnect
                            </button>
                            <button className="btn btn-quiet btn-sm" onClick={() => setConfirmDisconnect(null)}>
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button className="btn btn-danger btn-sm" onClick={() => setConfirmDisconnect(p.key)} disabled={working}>
                            Disconnect {p.name}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </main>
    </div>
  );
}
