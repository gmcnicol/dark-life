import Link from "next/link";
import type { ReactNode } from "react";
import KeyboardShortcuts from "./keyboard-shortcuts";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen grid grid-cols-[16rem_1fr]">
      <aside className="bg-zinc-900 text-zinc-100 p-4">
        <nav className="space-y-2">
          <Link
            href="/"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Home
          </Link>
          <Link
            href="/dashboard"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Dashboard
          </Link>
          <Link
            href="/board"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Board
          </Link>
          <Link
            href="/settings"
            className="block hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Settings
          </Link>
        </nav>
      </aside>
      <div className="flex flex-col bg-background text-foreground">
        <header className="h-14 border-b border-zinc-800 flex items-center px-4 gap-4">
          <span className="font-semibold">Dark Life</span>
          <input
            id="global-search"
            type="search"
            placeholder="Search"
            className="ml-auto max-w-xs w-full rounded border border-input bg-background px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </header>
        <main className="flex-1 p-4">{children}</main>
        <KeyboardShortcuts />
      </div>
    </div>
  );
}
