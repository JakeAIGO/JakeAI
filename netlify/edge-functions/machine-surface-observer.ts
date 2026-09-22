import { observe } from "./_agent-observer.ts";

export default async (request: Request, context: any) => observe(request, context, true);

export const config = {
  path: [
    "/llms.txt",
    "/robots.txt",
    "/sitemap.xml",
    "/catalog.json",
    "/workflow-registry.json",
    "/.well-known/*",
    "/agent-catalog/*"
  ]
};
