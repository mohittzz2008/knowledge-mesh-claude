import Link from 'next/link';
import { Navbar } from '@/components/ui/Navbar';
import { SkillGraph } from '@/components/landing/SkillGraph';

const PLATFORMS = ['GitHub', 'LeetCode', 'HackerRank', 'Codeforces', 'AtCoder', 'CodeChef', 'Codewars', 'GeeksforGeeks', 'Exercism'];

const STEPS = [
  {
    n: '1',
    title: 'Connect your accounts',
    body: 'Enter a username. Knowledge Mesh reads only what is public on that profile: solved problems, tags, ratings, repositories.',
  },
  {
    n: '2',
    title: 'See what it shows',
    body: 'Each solved problem or project counts as evidence for the skills it involves. Skills with little evidence are marked as such instead of guessed.',
  },
  {
    n: '3',
    title: 'Practice what is thin',
    body: 'The learning path picks the next skill, a difficulty that fits your history, and problems you have not already solved elsewhere.',
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />

      <main className="flex-1">
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div>
            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
              Your practice history, turned into a skill map.
            </h1>
            <p className="mt-5 max-w-lg text-base text-mute">
              Connect the coding sites you already use. Knowledge Mesh combines them into one view of what you have
              actually demonstrated, where the evidence is thin, and what to practice next.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/platforms" className="btn btn-primary">
                Connect a platform
              </Link>
              <Link href="/dashboard" className="btn btn-secondary">
                Open dashboard
              </Link>
            </div>
          </div>

          <figure className="panel p-5">
            <SkillGraph />
            <figcaption className="mt-2 text-xs text-faint">Example data. Your own map is built from your accounts.</figcaption>
          </figure>
        </section>

        <section className="border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
            <h2 className="text-xl font-semibold">How it works</h2>
            <ol className="mt-8 grid gap-8 sm:grid-cols-3">
              {STEPS.map((s) => (
                <li key={s.n}>
                  <span className="tnum font-mono text-sm text-accent">{s.n}</span>
                  <h3 className="mt-1 text-[15px] font-medium">{s.title}</h3>
                  <p className="mt-1.5 text-sm text-mute">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="border-t border-line">
          <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
            <h2 className="text-xl font-semibold">Supported platforms</h2>
            <ul className="mt-5 flex flex-wrap gap-2">
              {PLATFORMS.map((p) => (
                <li key={p} className="chip">
                  {p}
                </li>
              ))}
            </ul>
            <p className="mt-4 max-w-2xl text-sm text-mute">
              GeeksforGeeks has no public API, so it is read from the public profile page and can stop working if the
              site changes its layout.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-line py-6 text-sm text-faint">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 sm:px-6">
          <span>Knowledge Mesh</span>
          <nav className="flex gap-5" aria-label="Footer">
            <Link href="/dashboard" className="hover:text-ink">Dashboard</Link>
            <Link href="/platforms" className="hover:text-ink">Platforms</Link>
            <Link href="/learning-path" className="hover:text-ink">Learning path</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
