import Link from 'next/link';
import { AlertCircle, Loader2 } from 'lucide-react';
import { Navbar } from '@/components/ui/Navbar';

interface Props {
  mode: 'sign-in' | 'sign-up';
  verifying: boolean;
  email: string;
  code: string;
  loading: boolean;
  error: string | null;
  cooldown?: number;
  onEmail: (v: string) => void;
  onCode: (v: string) => void;
  onSubmitEmail: (e: React.FormEvent) => void;
  onSubmitCode: (e: React.FormEvent) => void;
  onGoogle: () => void;
  onResend?: () => void;
  onChangeEmail: () => void;
}

function Google() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden>
      <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.7 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.3 9 5 12 5z" />
      <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.8z" />
      <path fill="#FBBC05" d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.9 7.3C.7 9.7 0 12.3 0 15s.7 5.3 1.9 7.7l3.7-2.9z" />
      <path fill="#34A853" d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.3-6.4-5.2L1.9 16C3.7 19.7 7.5 23 12 23z" />
    </svg>
  );
}

export function AuthCard(p: Props) {
  const signIn = p.mode === 'sign-in';
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        <div className="panel w-full max-w-sm p-7">
          <h1 className="page-title">{signIn ? 'Sign in' : 'Create your account'}</h1>
          <p className="mt-1.5 text-sm text-mute">
            {p.verifying ? (
              <>We sent a 6-digit code to <span className="text-ink">{p.email}</span>.</>
            ) : (
              'We email you a one-time code. No password needed.'
            )}
          </p>

          {p.error && (
            <div role="alert" className="mt-5 flex items-start gap-2 rounded-md border border-bad/30 bg-bad/10 px-3 py-2.5 text-[13px] text-ink-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-bad" aria-hidden />
              <span>{p.error}</span>
            </div>
          )}

          {!p.verifying ? (
            <form onSubmit={p.onSubmitEmail} className="mt-6 space-y-4">
              <div>
                <label htmlFor="email" className="label mb-1.5 block">Email address</label>
                <input id="email" type="email" required autoComplete="email" className="input" placeholder="you@example.com" value={p.email} onChange={(e) => p.onEmail(e.target.value)} />
              </div>
              <button type="submit" disabled={p.loading || !p.email.trim()} className="btn btn-primary w-full">
                {p.loading && <Loader2 className="h-4 w-4 animate-spin" />} Email me a code
              </button>
              <div className="flex items-center gap-3 text-xs text-faint">
                <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
              </div>
              <button type="button" onClick={p.onGoogle} className="btn btn-secondary w-full">
                <Google /> Continue with Google
              </button>
            </form>
          ) : (
            <form onSubmit={p.onSubmitCode} className="mt-6 space-y-4">
              <div>
                <label htmlFor="code" className="label mb-1.5 block">Verification code</label>
                <input id="code" inputMode="numeric" autoComplete="one-time-code" required maxLength={6} className="input text-center font-mono text-lg tracking-[0.4em]" placeholder="123456" value={p.code} onChange={(e) => p.onCode(e.target.value)} />
              </div>
              <button type="submit" disabled={p.loading || p.code.length < 6} className="btn btn-primary w-full">
                {p.loading && <Loader2 className="h-4 w-4 animate-spin" />} {signIn ? 'Sign in' : 'Create account'}
              </button>
              <div className="flex items-center justify-between text-[13px]">
                {p.onResend ? (
                  <button type="button" onClick={p.onResend} disabled={(p.cooldown ?? 0) > 0 || p.loading} className="text-accent hover:underline disabled:text-faint disabled:no-underline">
                    {(p.cooldown ?? 0) > 0 ? `Resend in ${p.cooldown}s` : 'Resend code'}
                  </button>
                ) : <span />}
                <button type="button" onClick={p.onChangeEmail} className="text-mute hover:text-ink">Use a different email</button>
              </div>
            </form>
          )}

          <p className="mt-6 border-t border-line pt-4 text-center text-[13px] text-mute">
            {signIn ? 'New here? ' : 'Already have an account? '}
            <Link href={signIn ? '/sign-up' : '/sign-in'} className="text-accent hover:underline">
              {signIn ? 'Create an account' : 'Sign in'}
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
