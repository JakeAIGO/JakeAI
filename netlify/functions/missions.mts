import { getStore, getDeployStore } from "@netlify/blobs";

function store() {
  return Netlify.context?.deploy?.context === "production"
    ? getStore("jakeai-missions", { consistency: "strong" })
    : getDeployStore("jakeai-missions");
}

function text(value, max = 5000) {
  return String(value ?? "").trim().slice(0, max);
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function classify(signal, outcome, boundaries) {
  const all = (signal + " " + outcome + " " + boundaries).toLowerCase();
  let category = "general";
  if (/solar|battery|energy|utility|grid|electric|rfp|rfq/.test(all)) category = "energy";
  else if (/roof|construction|contractor|bid|permit/.test(all)) category = "construction";
  else if (/manufactur|factory|machine|quality|downtime|supplier/.test(all)) category = "manufacturing";
  else if (/farm|crop|agricultur|field|livestock/.test(all)) category = "agriculture";
  else if (/video|music|film|creator|media|youtube|game/.test(all)) category = "creator-media";
  else if (/agent|workflow|automation|api|model|llm|software/.test(all)) category = "ai-operations";

  const missing = [];
  if (signal.length < 20) missing.push("problem_detail");
  if (outcome.length < 10) missing.push("desired_outcome");
  return {
    category,
    completeness: missing.length ? "needs_detail" : "ready_for_triage",
    missing,
    priority: "normal",
  };
}

async function publicSummary(s) {
  const { blobs } = await s.list({ prefix: "mission/" });
  const counts = {};
  let latest = null;
  for (const b of blobs) {
    const m = await s.get(b.key, { type: "json" });
    if (!m) continue;
    counts[m.status || "unknown"] = (counts[m.status || "unknown"] || 0) + 1;
    if (!latest || String(m.created || "") > latest) latest = String(m.created || "");
  }
  return {
    service: "JakeAI Mission Intake",
    accepting: true,
    total: blobs.length,
    counts,
    latest_received_at: latest,
    public_detail: "aggregate-only",
  };
}

export default async (req) => {
  const s = store();

  if (req.method === "POST") {
    let body;
    try {
      body = await req.json();
    } catch {
      return Response.json({ error: "Invalid JSON" }, { status: 400 });
    }

    if (text(body?.website, 200)) {
      return Response.json({ ok: true }, { status: 202 });
    }

    const signal = text(body?.signal);
    const outcome = text(body?.outcome);
    const boundaries = text(body?.boundaries);
    const idempotencyKey = text(body?.idempotency_key, 200);

    if (!signal || !idempotencyKey || idempotencyKey.length < 16) {
      return Response.json({ error: "Missing mission data or idempotency key" }, { status: 400 });
    }

    const keyHash = await sha256(idempotencyKey);
    const id = "JAI-MISSION-" + keyHash.slice(0, 16).toUpperCase();
    const existing = await s.get("mission/" + id, { type: "json" });

    if (existing) {
      return Response.json({
        ok: true,
        duplicate: true,
        mission: {
          id: existing.id,
          status: existing.status,
          created: existing.created,
          updated: existing.updated,
          triage: existing.triage,
        },
      });
    }

    const now = new Date().toISOString();
    const triage = classify(signal, outcome, boundaries);
    const status = triage.completeness === "needs_detail" ? "needs_information" : "received";
    const mission = {
      schema: "jakeai-mission-v2",
      id,
      signal,
      outcome,
      boundaries,
      status,
      triage,
      created: now,
      updated: now,
      source: "commission-bay",
      controls: {
        human_release_gate: true,
        outbound_authorized: false,
      },
      events: [{ at: now, type: "received", source: "commission-bay" }],
    };

    await s.setJSON("mission/" + id, mission);
    await s.setJSON("queue/" + status + "/" + String(Date.now()).padStart(13, "0") + "-" + id, {
      mission_id: id,
      status,
      created: now,
    });

    return Response.json({
      ok: true,
      duplicate: false,
      mission: { id, status, created: now, updated: now, triage },
    }, { status: 202 });
  }

  if (req.method === "GET") {
    return Response.json(await publicSummary(s), {
      headers: { "Cache-Control": "no-store" },
    });
  }

  return new Response("Method not allowed", {
    status: 405,
    headers: { Allow: "GET, POST" },
  });
};

export const config = { path: "/api/missions" };
