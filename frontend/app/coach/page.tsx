'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowRight, ChevronDown, ChevronUp, ExternalLink, Send } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';
import { PageHeader } from '@/components/ui/PageHeader';
import { sendCoachMessage, type EvidenceReference, type SuggestedAction } from '@/lib/api';

interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  status?: 'sending' | 'failed';
  intent?: string;
  confidence?: number;
  context_used?: Record<string, unknown>;
  evidence_references?: EvidenceReference[];
  suggested_actions?: SuggestedAction[];
  detected_mistake_patterns?: Array<Record<string, unknown>>;
}

const STARTERS: SuggestedAction[] = [
  { label: 'Why am I weak at recursion?', action_type: 'prompt', target_path: 'Why am I weak at recursion?' },
  { label: 'What should I practice next?', action_type: 'prompt', target_path: 'What should I practice next?' },
  { label: 'Open my skill graph', action_type: 'link', target_path: '/knowledge-mesh' },
];

const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export default function CoachPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openContext, setOpenContext] = useState<Record<string, boolean>>({});
  const endRef = useRef<HTMLDivElement>(null);
  const seq = useRef(0);
  const nextId = (prefix: string) => `${prefix}-${++seq.current}`;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, sending]);

  const send = async (text: string, retryId?: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    const id = retryId ?? nextId('user');

    setError(null);
    setSending(true);
    if (retryId) {
      setMessages(prev => prev.map(m => (m.id === id ? { ...m, status: 'sending' } : m)));
    } else {
      setMessages(prev => [
        ...prev,
        { id, sender: 'user', text: trimmed, timestamp: now(), status: 'sending' },
      ]);
      setInput('');
    }

    try {
      const res = await sendCoachMessage(trimmed, conversationId);
      if (!conversationId) setConversationId(res.conversation_id);
      const aiMsg: ChatMessage = {
        id: res.message_id || nextId('ai'),
        sender: 'ai',
        text: res.answer,
        timestamp: now(),
        intent: res.intent,
        confidence: res.confidence,
        context_used: res.context_used,
        evidence_references: res.evidence_references,
        suggested_actions: res.suggested_actions,
        detected_mistake_patterns: res.detected_mistake_patterns,
      };
      setMessages(prev => [
        ...prev.map(m => (m.id === id ? { ...m, status: undefined } : m)),
        aiMsg,
      ]);
    } catch (err) {
      setMessages(prev => prev.map(m => (m.id === id ? { ...m, status: 'failed' } : m)));
      setError(err instanceof Error ? err.message : 'The coach could not answer. Try again.');
    } finally {
      setSending(false);
    }
  };

  const handleAction = (action: SuggestedAction) => {
    if (action.action_type === 'prompt') void send(action.target_path);
    else router.push(action.target_path);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
        <PageHeader
          title="Coach"
          description="Ask about your skill gaps and what to practice next. Answers are based on the work you have imported."
          actions={
            <Link href="/knowledge-mesh" className="btn btn-secondary btn-sm">
              Open skill graph
            </Link>
          }
        />

        <section className="panel flex h-[calc(100vh-15rem)] min-h-[480px] flex-col overflow-hidden" aria-label="Conversation with the coach">
          <div
            className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6"
            role="log"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.length === 0 && (
              <div className="mx-auto max-w-lg py-10 text-center">
                <h2 className="text-base font-semibold">What do you want to work on?</h2>
                <p className="mt-1.5 text-sm text-mute">
                  Ask a question, or start with one of these.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {STARTERS.map(a => (
                    <button key={a.label} type="button" onClick={() => handleAction(a)} className="btn btn-secondary btn-sm">
                      {a.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map(m => (
              <div key={m.id} className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-xl space-y-3 ${m.sender === 'user' ? 'text-right' : ''}`}>
                  <div
                    className={`rounded-lg px-4 py-3 text-left text-sm leading-relaxed whitespace-pre-wrap ${
                      m.sender === 'user'
                        ? `bg-raised border ${m.status === 'failed' ? 'border-bad' : 'border-line-strong'} text-ink`
                        : 'bg-surface border border-line text-ink-2'
                    }`}
                  >
                    {m.text}
                  </div>

                  <div className="flex items-center justify-between gap-3 text-xs text-faint">
                    <span className="tnum">
                      {m.sender === 'ai' && m.confidence != null && (
                        <>Confidence {Math.round(m.confidence * 100)}%{m.intent ? ` · ${m.intent.toLowerCase()}` : ''} · </>
                      )}
                      {m.status === 'sending' ? 'Sending' : m.timestamp}
                    </span>
                    {m.status === 'failed' && (
                      <span className="inline-flex items-center gap-2 text-bad">
                        Failed to send
                        <button type="button" onClick={() => void send(m.text, m.id)} disabled={sending} className="btn btn-secondary btn-sm">
                          Retry
                        </button>
                      </span>
                    )}
                  </div>

                  {m.detected_mistake_patterns && m.detected_mistake_patterns.length > 0 && (
                    <div className="rounded-md border border-line bg-surface px-3 py-2 text-left text-sm">
                      <p className="flex items-center gap-1.5 font-medium text-warn">
                        <AlertCircle className="h-4 w-4" aria-hidden />
                        Pattern to watch: {String(m.detected_mistake_patterns[0].title)}
                      </p>
                      <p className="mt-1 text-mute">{String(m.detected_mistake_patterns[0].description)}</p>
                    </div>
                  )}

                  {m.sender === 'ai' && m.context_used && (
                    <div className="rounded-md border border-line text-left">
                      <button
                        type="button"
                        onClick={() => setOpenContext(p => ({ ...p, [m.id]: !p[m.id] }))}
                        aria-expanded={!!openContext[m.id]}
                        className="flex w-full cursor-pointer items-center justify-between px-3 py-2 text-sm text-mute hover:text-ink"
                      >
                        What this answer is based on
                        {openContext[m.id] ? <ChevronUp className="h-4 w-4" aria-hidden /> : <ChevronDown className="h-4 w-4" aria-hidden />}
                      </button>
                      {openContext[m.id] && (
                        <div className="space-y-2 border-t border-line px-3 py-2.5 text-sm text-ink-2">
                          {Array.isArray((m.context_used as { grounded_platforms?: string[] }).grounded_platforms) &&
                          (m.context_used as { grounded_platforms: string[] }).grounded_platforms.length > 0 ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="label">Platforms</span>
                              {(m.context_used as { grounded_platforms: string[] }).grounded_platforms.map(p => (
                                <span key={p} className="chip">{p}</span>
                              ))}
                            </div>
                          ) : (
                            <p className="text-mute">No platform data was attached to this answer.</p>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {m.evidence_references && m.evidence_references.length > 0 && (
                    <div className="space-y-1.5 text-left">
                      <span className="label block">Sources</span>
                      <div className="flex flex-wrap gap-2">
                        {m.evidence_references.map((ref, idx) => {
                          const label = ref.repository ? `${ref.repository}${ref.file_path ? ` (${ref.file_path})` : ''}` : ref.title;
                          return ref.source_url ? (
                            <a key={idx} href={ref.source_url} target="_blank" rel="noreferrer" className="chip hover:border-accent hover:text-accent">
                              {label}
                              <ExternalLink className="h-3 w-3" aria-hidden />
                            </a>
                          ) : (
                            <Link key={idx} href="/code-intelligence" className="chip hover:border-accent hover:text-accent">
                              {label}
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {m.suggested_actions && m.suggested_actions.length > 0 && (
                    <div className="flex flex-wrap gap-2 text-left">
                      {m.suggested_actions.map((act, i) => (
                        <button key={i} type="button" onClick={() => handleAction(act)} disabled={sending && act.action_type === 'prompt'} className="btn btn-secondary btn-sm">
                          {act.label}
                          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {sending && <p className="text-sm text-mute">Coach is writing a reply…</p>}
            <div ref={endRef} />
          </div>

          {error && (
            <div role="alert" className="flex items-start gap-2 border-t border-line px-4 py-3 text-sm text-bad sm:px-6">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{error}</span>
            </div>
          )}

          <form
            onSubmit={e => {
              e.preventDefault();
              void send(input);
            }}
            className="flex items-end gap-2 border-t border-line p-3 sm:p-4"
          >
            <label htmlFor="coach-input" className="sr-only">Message to the coach</label>
            <textarea
              id="coach-input"
              rows={1}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void send(input);
                }
              }}
              placeholder="Ask about a skill, a mistake, or what to practice (Shift+Enter for a new line)"
              className="input h-auto max-h-32 min-h-[2.75rem] flex-1 resize-none py-2.5"
            />
            <button type="submit" disabled={sending || !input.trim()} className="btn btn-primary h-11 shrink-0">
              Send <Send className="h-4 w-4" aria-hidden />
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
