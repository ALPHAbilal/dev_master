import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import { SessionProvider } from "@/lib/session";
import "./tutor.css";
import "./scan_stage.css";
import "./globals.css";
export const metadata: Metadata = {
  title: "Tutor — platform",
  description: "Learn your codebase, one unit at a time.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <SessionProvider>{children}</SessionProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
