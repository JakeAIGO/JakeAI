export default async (req: Request) => {
  if (req.method !== "POST") return new Response("Method Not Allowed", { status: 405 });

  const secret = Netlify.env.get("JAKEAI_COMMERCE_PREVIEW_KEY");
  if (!secret) return new Response("Preview authorization unavailable", { status: 503 });

  const incoming = new URL(req.url);
  const upstreamPath = incoming.pathname.replace(/^\/commerce-preview-api/, "");
  const upstream = new URL(upstreamPath + incoming.search, "https://commerce-wallet-preview-production.up.railway.app");

  const headers = new Headers(req.headers);
  headers.set("X-JakeAI-Preview-Key", secret);
  headers.delete("host");
  headers.delete("cookie");
  headers.delete("authorization");

  return fetch(upstream, {
    method: "POST",
    headers,
    body: req.body,
    redirect: "manual",
  });
};

export const config = {
  path: "/commerce-preview-api/*",
};
