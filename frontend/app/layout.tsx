import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
// Fonts are self-hosted from npm packages (no build-time call to Google Fonts).
import "@fontsource-variable/schibsted-grotesk";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Knowledge Mesh",
  description:
    "Connect the coding platforms you use. Knowledge Mesh maps the skills your work actually evidences, shows where the evidence is thin, and suggests what to practice next.",
};

const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const inner = (
    <html lang="en" className="h-full antialiased dark">
      <body className="min-h-full flex flex-col bg-canvas text-ink">{children}</body>
    </html>
  );

  // When a real Clerk publishable key is configured (production or a personal
  // Clerk dev instance), wrap with ClerkProvider for full authentication.
  // In local-dev mode (no key set) the app runs without Clerk: the backend
  // honours X-Clerk-User-Id with ALLOW_INSECURE_DEV_AUTH=true, and
  // NEXT_PUBLIC_DEV_USER_ID is injected by getAuthHeaders() in lib/api.ts.
  if (clerkKey) {
    return <ClerkProvider publishableKey={clerkKey}>{inner}</ClerkProvider>;
  }

  return inner;
}
