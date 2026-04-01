import type { Metadata } from "next";
import QueryProvider from "@/lib/query-provider";
import ThemeProvider from "@/lib/theme-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nelson Freight — AI Logistics Platform",
  description: "AI-powered logistics command center for freight forwarding",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen">
        <ThemeProvider>
          <QueryProvider>{children}</QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
