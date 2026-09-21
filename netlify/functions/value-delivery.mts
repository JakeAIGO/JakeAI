const CATALOG_URL = "https://jakeaiofficial.com/catalog.json";

type Capability = {
  id?: string;
  slug?: string;
  name?: string;
  summary?: string;
  problem_signals?: string[];
  category?: string[];
  lifecycle_status?: string;
  publication_status?: string;
  human_url?: string;
  commerce?: { mode?: string; purchasable?: boolean; reason?: string };
  invocation?: { mode?: string; endpoint?: string | null };
  trust?: { human_release_gate?: boolean; provenance?: string; notice?: string };
};

function safeText(value: unknown, max = 2000) {
  return String(value ?? "").trim().slice(0, max);
}

function tokens(value: string) {
  return new Set(
    value.toLowerCase()
      .replace(/[^a-z0-9\s/-]/g, " ")
      .split(/\s+/)
      .filter((x) => x.length > 2)
  );
}

function score(problem: string, cap: Capability) {
  const p = problem.toLowerCase();
  const pTokens = tokens(problem);
  let total = 0;
  for (const signal of cap.problem_signals || []) {
    const s = signal.toLowerCase();
    if (p.includes(s)) total += 8;
    for (const t of tokens(signal)) if (pTokens.has(t)) total += 2;
  }
  for (const t of tokens([cap.name, cap.summary, ...(cap.category || [])].filter(Boolean).join(" "))) {
    if (pTokens.has(t)) total += 1;
  }
  return total;
}

export default async (req: Request) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "POST", "Cache-Control": "no-store" },
    });
  }

  let body: any;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const problem = safeText(body?.problem, 2000);
  const source = safeText(body?.source || "unknown", 80);
  if (problem.length < 3) {
    return Response.json({ error: "Problem is required" }, { status: 400 });
  }

  const requestId = crypto.randomUUID();
  const now = new Date().toISOString();

  try {
    const catalogRsp = await fetch(CATALOG_URL, {
      headers: { Accept: "application/json" },
    });
    if (!catalogRsp.ok) throw new Error("catalog unavailable");
    const catalog = await catalogRsp.json() as { capabilities?: Capability[] };
    const ranked = (catalog.capabilities || [])
      .map((cap) => ({ cap, score: score(problem, cap) }))
      .sort((a, b) => b.score - a.score);

    const best = ranked[0];
    const matched = !!best && best.score > 0;
    const cap = matched ? best.cap : null;

    console.log("JAKEAI_VALUE_DELIVERY", JSON.stringify({
      request_id: requestId,
      at: now,
      source,
      outcome: matched ? "matched" : "discovery",
      capability_id: cap?.id || null,
      score: matched ? best.score : 0,
      execution_authorized: false,
    }));

    return Response.json({
      request_id: requestId,
      at: now,
      status: matched ? "matched" : "discovery",
      capability: cap ? {
        id: cap.id,
        slug: cap.slug,
        name: cap.name,
        summary: cap.summary,
        lifecycle_status: cap.lifecycle_status,
        publication_status: cap.publication_status,
        human_url: cap.human_url,
        commerce: cap.commerce,
        invocation: cap.invocation,
      } : null,
      summary: cap?.summary || "No existing public JakeAI capability confidently matches this problem yet.",
      next_step: cap
        ? "Review the matched capability. Any consequential or external action remains human-approved."
        : "Route this problem to JakeAI Discovery for classification, composition, or evaluation as a potential new workflow.",
      controls: {
        execution_authorized: false,
        outbound_authorized: false,
        human_release_gate: true,
      },
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({
      request_id: requestId,
      status: "error",
      error: "JakeAI capability catalog is temporarily unavailable",
      controls: {
        execution_authorized: false,
        outbound_authorized: false,
        human_release_gate: true,
      },
    }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
};

export const config = { path: "/api/value-delivery" };
