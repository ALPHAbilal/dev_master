// Read the client-facing var directly and let Next inline it natively.
// Do NOT re-inject it via `env:` — that clobbers the value set in Vercel/hosting.
const transport = process.env.NEXT_PUBLIC_TRANSPORT || "stub";
if (!["stub", "live"].includes(transport))
  throw new Error("NEXT_PUBLIC_TRANSPORT must be live or stub");
/** @type {import('next').NextConfig} */
const config = { agentRules: false };
export default config;
