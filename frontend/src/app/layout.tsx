import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";
import { AuthProvider } from "@/features/auth";

export const metadata: Metadata = {
  title: "Rapier Bench",
  description: "Domain-aware AI benchmarking platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body className="flex min-h-full flex-col bg-zinc-950 text-zinc-100 font-sans antialiased">
        <AuthProvider>
          <Header />
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </main>
          <footer className="border-t border-zinc-800 bg-zinc-950 px-4 py-6 text-xs text-zinc-400 sm:px-6 lg:px-8">
            <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 sm:flex-row">
              <p>Rapier Bench — Domain-aware AI benchmarking platform.</p>
              <p className="text-zinc-500">
                Empirical, reproducible evaluation.
              </p>
            </div>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
