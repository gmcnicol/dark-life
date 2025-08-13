import Link from "next/link";
import type { ReactNode } from "react";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen grid grid-cols-[16rem_1fr]">
      <aside className="bg-zinc-900 text-zinc-100 p-4">
        <nav className="space-y-2">
          <Link href="/" className="block hover:underline">
            Home
          </Link>
          <Link href="/dashboard" className="block hover:underline">
            Dashboard
          </Link>
          <Link href="/settings" className="block hover:underline">
            Settings
          </Link>
        </nav>
      </aside>
      <div className="flex flex-col bg-background text-foreground">
        <header className="h-14 border-b border-zinc-800 flex items-center px-4">
          <span className="font-semibold">Dark Life</span>
        </header>
        <main className="flex-1 p-4">{children}</main>
      </div>
    </div>
  );
}
