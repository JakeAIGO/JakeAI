import { getStore, getDeployStore } from "@netlify/blobs";

function store() {
  return Netlify.context?.deploy?.context === "production"
    ? getStore("jakeai-missions", { consistency: "strong" })
    : getDeployStore("jakeai-missions");
}

export default async (req) => {
  const s = store();
  if (req.method === "POST") {
    const body = await req.json();
    if (!body?.id || !body?.signal) return Response.json({ error: "Missing mission data" }, { status: 400 });
    const mission = { id: String(body.id).slice(0,80), signal: String(body.signal).slice(0,5000), outcome: String(body.outcome||"").slice(0,5000), boundaries: String(body.boundaries||"").slice(0,5000), status: "draft", updated: new Date().toISOString() };
    await s.setJSON("mission/"+mission.id, mission);
    return Response.json({ ok: true, mission });
  }
  if (req.method === "GET") {
    const { blobs } = await s.list({ prefix: "mission/" });
    const missions = [];
    for (const b of blobs.slice(-50).reverse()) {
      const m = await s.get(b.key, { type: "json" });
      if (m) missions.push(m);
    }
    return Response.json({ missions });
  }
  return new Response("Method not allowed", { status: 405 });
};

export const config = { path: "/api/missions" };
