export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="page-title">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-mute">{description}</p>}
      </div>
      {actions}
    </div>
  );
}
