import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { motion } from "motion/react";
import { Link, type LinkProps } from "react-router-dom";
import { BionicReadingToggle } from "@/components/bionic-text";
import { READER_SIZE_PRESETS, type ReaderSizeId } from "@/lib/reader-preferences";
import { cn } from "@/lib/utils";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  aside,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      className="grid gap-5 rounded-[2rem] border border-white/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.09),rgba(255,255,255,0.03))] p-6 shadow-[0_24px_100px_rgba(0,0,0,0.22)] backdrop-blur-xl lg:grid-cols-[minmax(0,1fr)_19rem]"
    >
      <div className="space-y-4">
        <p className="text-[0.72rem] font-semibold uppercase tracking-[0.32em] text-[var(--muted)]">
          {eyebrow}
        </p>
        <div className="space-y-3">
          <h1 className="font-display text-4xl tracking-[-0.03em] text-white md:text-5xl">
            {title}
          </h1>
          <p className="max-w-3xl text-sm leading-7 text-[var(--text-soft)] md:text-base">
            {description}
          </p>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>
      {aside ? (
        <div className="rounded-[1.5rem] border border-white/10 bg-black/15 p-4">{aside}</div>
      ) : null}
    </motion.section>
  );
}

export function Panel({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-[1.75rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.03))] p-5 shadow-[0_20px_70px_rgba(0,0,0,0.16)] backdrop-blur-md",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function SurfaceRail({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn("space-y-4 lg:sticky lg:top-4 lg:self-start", className)}>{children}</div>;
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2">
        {eyebrow ? (
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
            {eyebrow}
          </p>
        ) : null}
        <h2 className="text-xl font-semibold tracking-[-0.02em] text-white">{title}</h2>
        {description ? <p className="max-w-2xl text-sm leading-6 text-[var(--text-soft)]">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function PageActions({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("flex flex-col gap-3", className)}>{children}</div>;
}

export function PageStatusBar({
  children,
  className,
  description,
}: {
  children: ReactNode;
  className?: string;
  description?: ReactNode;
}) {
  return (
    <Panel className={cn("space-y-3 p-4", className)}>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
      {description ? <p className="text-sm text-[var(--text-soft)]">{description}</p> : null}
    </Panel>
  );
}

export function HintPanel({
  eyebrow = "Operator guidance",
  title,
  description,
  children,
  className,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <Panel className={cn("space-y-4 p-4", className)}>
      <SectionHeading eyebrow={eyebrow} title={title} description={description} />
      {children}
    </Panel>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  timestamp,
}: {
  label: string;
  value: ReactNode;
  detail: string;
  timestamp?: ReactNode;
}) {
  return (
    <Panel className="space-y-4 p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
          {label}
        </p>
        {timestamp ? <p className="text-[0.68rem] uppercase tracking-[0.2em] text-[var(--muted)]">{timestamp}</p> : null}
      </div>
      <div className="flex items-end justify-between gap-4">
        <p className="font-display text-4xl tracking-[-0.04em] text-white">{value}</p>
        <p className="max-w-[12rem] text-right text-xs leading-5 text-[var(--text-soft)]">{detail}</p>
      </div>
    </Panel>
  );
}

export function StatusBadge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "success" | "warning" | "danger";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em]",
        tone === "neutral" && "border-white/10 bg-white/5 text-[var(--text-soft)]",
        tone === "accent" && "border-cyan-400/30 bg-cyan-400/12 text-cyan-100",
        tone === "success" && "border-emerald-400/30 bg-emerald-400/12 text-emerald-100",
        tone === "warning" && "border-amber-400/30 bg-amber-400/12 text-amber-100",
        tone === "danger" && "border-rose-400/30 bg-rose-400/12 text-rose-100",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Panel className="flex min-h-56 flex-col items-start justify-center gap-4 p-6">
      <StatusBadge tone="neutral">No items</StatusBadge>
      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="max-w-xl text-sm leading-6 text-[var(--text-soft)]">{description}</p>
      </div>
      {action}
    </Panel>
  );
}

export function LoadingState({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <Panel className={cn("flex min-h-44 items-center gap-4", className)}>
      <span className="h-3 w-3 animate-pulse rounded-full bg-cyan-300" />
      <p className="text-sm text-[var(--text-soft)]">{label}</p>
    </Panel>
  );
}

export function ActionButton({
  children,
  tone = "primary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-full px-4 py-2.5 text-sm font-semibold transition duration-150 disabled:cursor-not-allowed disabled:opacity-50",
        tone === "primary" &&
          "bg-[linear-gradient(135deg,#8be9fd,#56d6ff)] text-slate-950 shadow-[0_12px_30px_rgba(86,214,255,0.25)] hover:-translate-y-0.5",
        tone === "secondary" &&
          "border border-white/12 bg-white/8 text-white hover:-translate-y-0.5 hover:bg-white/12",
        tone === "ghost" && "text-[var(--text-soft)] hover:bg-white/8 hover:text-white",
        tone === "danger" &&
          "border border-rose-400/25 bg-rose-400/10 text-rose-100 hover:-translate-y-0.5",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function ActionLink({
  className,
  tone = "primary",
  ...props
}: LinkProps & {
  tone?: "primary" | "secondary";
}) {
  return (
    <Link
      className={cn(
        "inline-flex items-center justify-center rounded-full px-4 py-2.5 text-sm font-semibold transition duration-150 hover:-translate-y-0.5",
        tone === "primary" &&
          "bg-[linear-gradient(135deg,#8be9fd,#56d6ff)] text-slate-950 shadow-[0_12px_30px_rgba(86,214,255,0.25)]",
        tone === "secondary" && "border border-white/12 bg-white/8 text-white hover:bg-white/12",
        className,
      )}
      {...props}
    />
  );
}

export function ReaderControls({
  size,
  onSizeChange,
  showBionicToggle = true,
  className,
  compact = false,
}: {
  size: ReaderSizeId;
  onSizeChange: (size: ReaderSizeId) => void;
  showBionicToggle?: boolean;
  className?: string;
  compact?: boolean;
}) {
  const activeIndex = Math.max(
    READER_SIZE_PRESETS.findIndex((preset) => preset.id === size),
    0,
  );

  const setIndex = (nextIndex: number) => {
    const preset = READER_SIZE_PRESETS[nextIndex];
    if (preset) {
      onSizeChange(preset.id);
    }
  };

  return (
    <div className={cn(compact ? "space-y-3" : "space-y-4", className)}>
      <div className={cn("gap-4", compact ? "grid md:grid-cols-[auto_minmax(0,1fr)] md:items-center" : "space-y-4")}>
        {showBionicToggle ? <BionicReadingToggle /> : null}
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
              Story text size
            </p>
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-white/78">
              {READER_SIZE_PRESETS[activeIndex]?.label ?? "Comfortable"}
            </span>
          </div>
          <div className="flex items-center gap-3 rounded-[1rem] border border-white/10 bg-white/[0.04] px-3 py-3">
            <button
              type="button"
              onClick={() => setIndex(Math.max(0, activeIndex - 1))}
              disabled={activeIndex === 0}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/12 bg-black/20 text-sm font-semibold text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Decrease font size"
            >
              A-
            </button>
            <input
              type="range"
              min={0}
              max={READER_SIZE_PRESETS.length - 1}
              step={1}
              value={activeIndex}
              onChange={(event) => setIndex(Number(event.target.value))}
              className="reader-slider min-w-0 flex-1 accent-cyan-300"
              aria-label="Story text size"
            />
            <button
              type="button"
              onClick={() => setIndex(Math.min(READER_SIZE_PRESETS.length - 1, activeIndex + 1))}
              disabled={activeIndex === READER_SIZE_PRESETS.length - 1}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/[0.12] text-sm font-semibold text-cyan-50 transition hover:bg-cyan-300/[0.2] disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Increase font size"
            >
              A+
            </button>
          </div>
          <div className="flex items-center justify-between gap-2 text-[0.68rem] uppercase tracking-[0.16em] text-[var(--muted)]">
            {READER_SIZE_PRESETS.map((preset) => (
              <span key={preset.id}>{preset.label}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function readerStyleVars(fontSize: string, lineHeight: string): CSSProperties {
  return {
    "--reader-font-size": fontSize,
    "--reader-line-height": lineHeight,
  } as CSSProperties;
}

export function DataGridSurface({
  className,
  children,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  variant?: "default" | "dense";
}) {
  return (
    <div
      className={cn(
        "ag-theme-quartz-dark data-grid-surface overflow-hidden rounded-[1.35rem] border border-white/10",
        variant === "dense" && "data-grid-surface--dense",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
