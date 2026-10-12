// Read the client-facing var directly and let Next inline it natively.
// Do NOT re-inject it via `env:` — that clobbers the value set in Vercel/hosting.
const transport = process.env.NEXT_PUBLIC_TRANSPORT || "stub";
if (!["stub", "live"].includes(transport))
  throw new Error("NEXT_PUBLIC_TRANSPORT must be live or stub");
/** @type {import('next').NextConfig} */
// The development badge sits on top of the sidebar rail's expand button.
const config = { agentRules: false, devIndicators: false };
export default config;
