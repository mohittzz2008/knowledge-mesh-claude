import { platformMeta } from '@/lib/platforms';

export function PlatformMark({ id, name, size = 36 }: { id: string; name?: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-md border border-line-strong bg-raised font-mono text-[11px] font-medium text-ink-2"
      style={{ width: size, height: size }}
    >
      {platformMeta(id, name).mark}
    </span>
  );
}
