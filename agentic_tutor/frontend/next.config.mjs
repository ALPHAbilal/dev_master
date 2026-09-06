const transport = process.env.TRANSPORT || "stub";
if (!["stub", "live"].includes(transport))
  throw new Error("TRANSPORT must be live or stub");
/** @type {import('next').NextConfig} */
const config = { agentRules: false, env: { NEXT_PUBLIC_TRANSPORT: transport } };
export default config;
