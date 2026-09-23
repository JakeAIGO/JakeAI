import crypto from "node:crypto";

const json = (status, body) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json", "cache-control": "no-store" },
});

export default async (request) => {
  if (request.method !== "POST") return json(405, { error: "method not allowed" });

  const expected = Netlify.env.get("DISCORD_REGISTER_SECRET");
  const supplied = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!expected || !supplied) return json(404, { error: "not found" });

  const a = Buffer.from(expected);
  const b = Buffer.from(supplied);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return json(404, { error: "not found" });

  const token = Netlify.env.get("DISCORD_BOT_TOKEN");
  const applicationId = Netlify.env.get("DISCORD_APPLICATION_ID");
  if (!token || !applicationId) return json(503, { error: "registration credentials unavailable" });

  const commands = [
    {
      name: "problem",
      description: "Send a problem into JakeAI for triage",
      options: [{ type: 3, name: "text", description: "Describe the problem", required: true }],
    },
    { name: "status", description: "Check the JakeAI Discord bridge" },
  ];

  const response = await fetch(`https://discord.com/api/v10/applications/${applicationId}/commands`, {
    method: "PUT",
    headers: { authorization: `Bot ${token}`, "content-type": "application/json" },
    body: JSON.stringify(commands),
  });

  const body = await response.text();
  return new Response(body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") || "application/json", "cache-control": "no-store" },
  });
};

export const config = { path: "/.jakeai/admin/discord-register" };
