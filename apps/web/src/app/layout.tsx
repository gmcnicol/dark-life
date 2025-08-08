import type { Metadata } from "next";
import Image from "next/image";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Dark Life",
  description: "Story editing suite",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-neutral-950 text-gray-100">
        <Providers>
          <header className="flex items-center gap-2 p-4 border-b border-neutral-800">
            <Image src="/logo.svg" alt="Dark Life logo" width={24} height={24} />
            <span className="font-semibold">Dark Life</span>
          </header>
          {children}
        </Providers>
      </body>
    </html>
  );
}
