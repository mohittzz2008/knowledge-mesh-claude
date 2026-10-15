'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu, X } from 'lucide-react';
import { fetchHealth } from '@/lib/api';

// Clerk UI components are only imported when a publishable key is configured.
// This avoids ClerkProvider-not-found errors in local dev mode (no key set).
const hasClerkKey = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

// Lazily wire up the Clerk auth slot so the module is never evaluated without a provider.
let ClerkAuthSlot: React.ComponentType | null = null;
if (hasClerkKey) {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const clerk = require('@clerk/nextjs') as typeof import('@clerk/nextjs');
  const { UserButton, SignedIn, SignedOut, SignInButton } = clerk;
  ClerkAuthSlot = function ClerkSlot() {
    return (
      <>
        <SignedIn>
          <UserButton appearance={{ elements: { avatarBox: 'h-8 w-8' } }} />
        </SignedIn>
        <SignedOut>
          <SignInButton mode="modal">
            <button className="btn btn-primary btn-sm">Sign in</button>
          </SignInButton>
        </SignedOut>
      </>
    );
  };
}

const NAV = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/knowledge-mesh', label: 'Skill map' },
  { href: '/learning-path', label: 'Learning path' },
  { href: '/coach', label: 'Coach' },
  { href: '/code-lab', label: 'Code Lab' },
  { href: '/code-intelligence', label: 'Code analysis' },
  { href: '/platforms', label: 'Platforms' },
];

function LogoMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden>
      <path d="M5 6l6 4 6-4M5 16l6-4 6 4M5 6v10M17 6v10" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
      <circle cx="5" cy="6" r="2" fill="currentColor" />
      <circle cx="17" cy="6" r="2" fill="currentColor" />
      <circle cx="11" cy="10" r="2" fill="currentColor" />
      <circle cx="5" cy="16" r="2" fill="currentColor" />
      <circle cx="17" cy="16" r="2" fill="currentColor" />
    </svg>
  );
}

export function Navbar() {
  const pathname = usePathname();
  const [api, setApi] = useState<'checking' | 'up' | 'down'>('checking');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    async function check() {
      const h = await fetchHealth();
      if (alive) setApi(h && h.status === 'ok' ? 'up' : 'down');
    }
    check();
    const id = setInterval(check, 60000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const link = (href: string) =>
    pathname === href || pathname.startsWith(href + '/')
      ? 'text-ink bg-raised'
      : 'text-mute hover:text-ink hover:bg-raised/60';

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 text-ink">
            <span className="text-accent"><LogoMark /></span>
            <span className="text-[15px] font-semibold tracking-tight">Knowledge Mesh</span>
          </Link>
          <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Main">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href} className={`rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors ${link(n.href)}`}>
                {n.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <span
            className="hidden items-center gap-1.5 text-xs text-faint sm:inline-flex"
            title={api === 'up' ? 'Backend reachable' : api === 'down' ? 'Backend not reachable' : 'Checking backend'}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${api === 'up' ? 'bg-ok' : api === 'down' ? 'bg-bad' : 'bg-faint'}`} />
            {api === 'down' ? 'API offline' : api === 'up' ? 'API' : '…'}
          </span>

          {/* Auth slot: full Clerk UI when a key is configured; dev badge otherwise */}
          {ClerkAuthSlot ? (
            <ClerkAuthSlot />
          ) : (
            <span
              className="hidden items-center rounded-md border border-line px-2 py-0.5 text-[11px] font-medium text-faint sm:inline-flex"
              title="Local dev mode — no Clerk account needed. Identity: dev_local_user"
            >
              Dev mode
            </span>
          )}

          <button
            onClick={() => setOpen(!open)}
            className="btn btn-quiet btn-sm lg:hidden"
            aria-label="Toggle navigation"
            aria-expanded={open}
          >
            {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-line px-4 py-2 lg:hidden" aria-label="Mobile">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} onClick={() => setOpen(false)} className={`block rounded-md px-3 py-2.5 text-sm font-medium ${link(n.href)}`}>
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
