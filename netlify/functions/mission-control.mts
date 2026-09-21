import { getStore, getDeployStore } from "@netlify/blobs";

const TOKEN_HASH = "c46d1f690e960090a16ee6a13f391f72f4db0b296d9effaaef6bc917d5456098";
const STATUSES = new Set([
  "received",
  "triaging",
  "investigating",
  "building",
  "testing",
  "needs_information",
  "ready_for_review",
  "closed",
]);

function store() {
  return Netlify.context?.deploy?.context === "production"
    ? getStore("jakeai-missions", { consistency: "strong" })
    : getDeployStore("jakeai-missions");
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(String(value || ""));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function authorized(req) {
  const header = req.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token || token.length < 20) return false;
  return (await sha256(token)) === TOKEN_HASH;
}

function safeText(value, max = 1000) {
  return String(value ?? "").trim().slice(0, max);
}

function publicMission(m) {
  return {
    id: m.id,
    signal: m.signal || "",
    outcome: m.outcome || "",
    boundaries: m.boundaries || "",
    status: m.status || "received",
    triage: m.triage || null,
    created: m.created || null,
    updated: m.updated || null,
    source: m.source || "commission-bay",
    controls: m.controls || { human_release_gate: true, outbound_authorized: false },
    events: Array.isArray(m.events) ? m.events.slice(-30) : [],
  };
}

export default async (req) => {
  if (!(await authorized(req))) {
    return Response.json({ error: "Unauthorized" }, {
      status: 401,
      headers: { "Cache-Control": "no-store" },
    });
  }

  const s = store();

  if (req.method === "GET") {
    const { blobs } = await s.list({ prefix: "mission/" });
    const missions = [];
    for (const b of blobs) {
      const m = await s.get(b.key, { type: "json" });
      if (m) missions.push(publicMission(m));
    }
    missions.sort((a, b) => String(b.created || b.updated || "").localeCompare(String(a.created || a.updated || "")));

    const counts = {};
    for (const m of missions) counts[m.status] = (counts[m.status] || 0) + 1;

    return Response.json({
      service: "JakeAI Mission Control",
      total: missions.length,
      counts,
      missions: missions.slice(0, 200),
      controls: {
        human_release_gate: true,
        outbound_default: "blocked",
      },
    }, { headers: { "Cache-Control": "no-store" } });
  }

  if (req.method === "PATCH") {
    let body;
    try {
      body = await req.json();
    } catch {
      return Response.json({ error: "Invalid JSON" }, { status: 400 });
    }

    const id = safeText(body?.id, 100);
    const status = safeText(body?.status, 40);
    const note = safeText(body?.note, 1200);

    if (!id || !STATUSES.has(status)) {
      return Response.json({ error: "Invalid mission update" }, { status: 400 });
    }

    const key = "mission/" + id;
    const mission = await s.get(key, { type: "json" });
    if (!mission) return Response.json({ error: "Mission not found" }, { status: 404 });

    const now = new Date().toISOString();
    mission.status = status;
    mission.updated = now;
    mission.controls = {
      ...(mission.controls || {}),
      human_release_gate: true,
      outbound_authorized: false,
    };
    mission.events = Array.isArray(mission.events) ? mission.events.slice(-99) : [];
    mission.events.push({
      at: now,
      type: "status_changed",
      status,
      note: note || undefined,
      source: "mission-control",
    });

    await s.setJSON(key, mission);
    await s.setJSON("queue/" + status + "/" + String(Date.now()).padStart(13, "0") + "-" + id, {
      mission_id: id,
      status,
      updated: now,
    });

    return Response.json({ ok: true, mission: publicMission(mission) }, {
      headers: { "Cache-Control": "no-store" },
    });
  }

  return new Response("Method not allowed", {
    status: 405,
    headers: { Allow: "GET, PATCH", "Cache-Control": "no-store" },
  });
};

export const config = { path: "/api/mission-control" };
