export default async (_request: Request, _context: any) => {
  return Response.json({
    status: "ready",
    observer_secret_configured: Boolean(Netlify.env.get("AGENT_OBSERVER_TOKEN"))
  }, {
    headers: {"cache-control":"no-store"}
  });
};

export const config = {
  path: "/agent-observer-health"
};
