import crypto from "node:crypto";

function verifySignature(rawBody, signature, timestamp, publicKey) {
  if (!signature || !timestamp || !publicKey) return false;
  try {
    const key = Buffer.from(publicKey.trim(), "hex");
    const sig = Buffer.from(signature, "hex");
    const message = Buffer.from(timestamp + rawBody);
    const spki = Buffer.concat([
      Buffer.from("302a300506032b6570032100", "hex"),
      key,
    ]);
    return crypto.verify(null, message, { key: spki, format: "der", type: "spki" }, sig);
  } catch {
    return false;
  }
}

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

export default async (request) => {
  if (request.method !== "POST") {
    return json(405, { error: "method not allowed" });
  }

  const rawBody = await request.text();
  const signature = request.headers.get("x-signature-ed25519");
  const timestamp = request.headers.get("x-signature-timestamp");
  const publicKey = Netlify.env.get("DISCORD_PUBLIC_KEY");

  if (!publicKey) {
    return json(503, { error: "DISCORD_PUBLIC_KEY is not configured" });
  }

  if (!verifySignature(rawBody, signature, timestamp, publicKey)) {
    return json(401, { error: "invalid request signature" });
  }

  let interaction;
  try {
    interaction = JSON.parse(rawBody);
  } catch {
    return json(400, { error: "invalid json" });
  }

  if (interaction.type === 1) {
    return json(200, { type: 1 });
  }

  if (interaction.type === 2) {
    const command = interaction.data?.name;

    if (command === "status") {
      return json(200, {
        type: 4,
        data: {
          content:
            "JakeAI Discord bridge is online. Production actions remain human-gated.",
        },
      });
    }

    if (command === "problem") {
      const problem =
        interaction.data?.options?.find((option) => option.name === "text")?.value ??
        "No problem text supplied.";

      return json(200, {
        type: 4,
        data: {
          content:
            `Received: ${problem}\n\nStatus: intake captured for JakeAI triage. No external action has been taken.`,
        },
      });
    }
  }

  return json(200, {
    type: 4,
    data: { content: "JakeAI received the interaction." },
  });
};

export const config = {
  path: "/discord/interactions",
};
