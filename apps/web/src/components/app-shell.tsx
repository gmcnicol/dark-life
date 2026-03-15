import Link from "next/link";
import type { ReactNode } from "react";
import KeyboardShortcuts from "./keyboard-shortcuts";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(251,191,36,0.12),_transparent_28%),linear-gradient(180deg,_#0f0b11,_#09070b)] md:grid md:grid-cols-[18rem_1fr]">
      <aside className="border-r border-zinc-900/80 bg-zinc-950/80 p-4 text-zinc-100 backdrop-blur">
        <nav className="space-y-2">
          <Link
            href="/dashboard"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Dashboard
          </Link>
          <Link
            href="/inbox"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Inbox
          </Link>
          <Link
            href="/board"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Board
          </Link>
          <Link
            href="/publish"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Publish Queue
          </Link>
          <Link
            href="/settings"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Settings
          </Link>
        </nav>
      </aside>
      <div className="flex flex-col text-foreground">
        <header className="flex h-14 items-center gap-4 border-b border-zinc-900 bg-zinc-950/60 px-4 backdrop-blur">
          <span className="font-semibold tracking-[0.25em] uppercase text-amber-200">Dark Life</span>
          <input
            id="global-search"
            type="search"
            placeholder="Search"
            className="ml-auto w-full max-w-xs rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
          />
        </header>
        <main className="flex-1 p-4 md:p-8">{children}</main>
        <KeyboardShortcuts />
      </div>
    </div>
  );
}
