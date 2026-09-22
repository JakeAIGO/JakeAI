async function postObservation(request: Request, context: any, response: Response, machineSurface: boolean) {
  const token = Netlify.env.get("AGENT_OBSERVER_TOKEN");
  if (!token) return;
  const url = new URL(request.url);
  let referrerHost = "";
  try {
    const ref = request.headers.get("referer") || "";
    referrerHost = ref ? new URL(ref).hostname : "";
  } catch (_) {}
  const body = {
    event_id: String(context.requestId || crypto.randomUUID()),
    path: url.pathname,
    method: request.method,
    user_agent: request.headers.get("user-agent") || "",
    client_ip: String(context.ip || ""),
    referrer_host: referrerHost,
    response_status: response.status,
    machine_surface: machineSurface,
  };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    await fetch(new URL("/api/v1/agent-observer/event", url.origin), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-jakeai-agent-observer": token,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (_) {
    // Observation must never break public delivery.
  } finally {
    clearTimeout(timer);
  }
}

export async function observe(request: Request, context: any, machineSurface = false) {
  const response = await context.next();
  if (request.method === "GET" || request.method === "HEAD") {
    await postObservation(request, context, response, machineSurface);
  }
  return response;
}
