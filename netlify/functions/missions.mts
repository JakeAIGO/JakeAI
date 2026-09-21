const UPSTREAM = "https://agent-commerce-network-production.up.railway.app";

export default async (req: Request) => {
  const target = req.method === "POST"
    ? UPSTREAM + "/v1/missions/intake"
    : UPSTREAM + "/v1/missions/public-status";

  if (!["GET", "POST"].includes(req.method)) {
    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "GET, POST", "Cache-Control": "no-store" },
    });
  }

  const init: RequestInit = {
    method: req.method,
    headers: { "Content-Type": "application/json" },
  };

  if (req.method === "POST") {
    init.body = await req.text();
  }

  try {
    const upstream = await fetch(target, init);
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json(
      { error: "Mission dispatcher is temporarily unavailable" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
};

export const config = { path: "/api/missions" };
