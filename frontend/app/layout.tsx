import type { Metadata } from "next";

import { SessionProvider } from "@/features/auth/session";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Alpha AI — Command Center",
    template: "%s | Alpha AI",
  },
  description:
    "AI-powered lead qualification and sales automation for real-estate teams. WhatsApp & SMS in, qualified leads and property matches out.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
