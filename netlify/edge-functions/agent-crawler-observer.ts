import { observe } from "./_agent-observer.ts";

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
