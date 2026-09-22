async function observe(request: Request, context: any, machineSurface: boolean) {
  const response = await context.next();
  if (request.method !== "GET" && request.method !== "HEAD") return response;
  const token = Netlify.env.get("AGENT_OBSERVER_TOKEN");
  if (!token) return response;

  const url = new URL(request.url);
  let referrerHost = "";
  try {
    const ref = request.headers.get("referer") || "";
    referrerHost = ref ? new URL(ref).hostname : "";
  } catch (_) {}

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    await fetch(new URL("/api/v1/agent-observer/event", url.origin), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-jakeai-agent-observer": token,
      },
      body: JSON.stringify({
        event_id: String(context.requestId || crypto.randomUUID()),
        path: url.pathname,
        method: request.method,
        user_agent: request.headers.get("user-agent") || "",
        client_ip: String(context.ip || ""),
        referrer_host: referrerHost,
        response_status: response.status,
        machine_surface: machineSurface,
      }),
      signal: controller.signal,
    });
  } catch (_) {
    // Measurement must never break public delivery.
  } finally {
    clearTimeout(timer);
  }
  return response;
}

export default async (request: Request, context: any) => observe(request, context, false);

export const config = {
  path: "/*",
  excludedPath: [
    "/api/*",
    "/mission-control/*",
    "/assets/*",
    "/*.css",
    "/*.js",
    "/*.jpg",
    "/*.jpeg",
    "/*.png",
    "/*.webp",
    "/*.svg",
    "/*.gif",
    "/*.mp4",
    "/*.webm",
    "/*.woff",
    "/*.woff2",
    "/*.ico"
  ],
  header: {
    "user-agent": ".*(Bot|bot|Crawler|crawler|Spider|spider|GPTBot|OAI-|ChatGPT|Claude|Perplexity|bingbot|Googlebot|Applebot|Amazonbot|Meta-ExternalAgent|CCBot).*"
  }
};
