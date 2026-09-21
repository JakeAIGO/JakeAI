const UPSTREAM = "https://agent-commerce-network-production.up.railway.app";

export default async (req: Request) => {
  if (!["GET", "PATCH"].includes(req.method)) {
    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "GET, PATCH", "Cache-Control": "no-store" },
    });
  }

  const authorization = req.headers.get("authorization") || "";
  if (!authorization.startsWith("Bearer ")) {
    return Response.json(
      { error: "Unauthorized" },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }

  const init: RequestInit = {
    method: req.method,
    headers: {
      Authorization: authorization,
      "Content-Type": "application/json",
    },
  };

  if (req.method === "PATCH") {
    init.body = await req.text();
  }

  try {
    const upstream = await fetch(UPSTREAM + "/v1/mission-control", init);
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
      { error: "Mission Control dispatcher is temporarily unavailable" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
};

export const config = { path: "/api/mission-control" };
