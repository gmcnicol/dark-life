import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import MswProvider from "@/mocks/msw-provider";
import QueryProvider from "@/components/query-provider";

export const metadata: Metadata = {
  title: "Dark Life Studio",
  description: "Self-hosted creepy story pipeline for Shorts and weekly YouTube cuts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-background text-foreground">
        <MswProvider />
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
