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
            "JakeAI Discord command channel is online. Problems route into the owned Mission Dispatcher; production actions remain human-gated.",
        },
      });
    }

    if (command === "problem") {
      const problem = String(
        interaction.data?.options?.find((option) => option.name === "text")?.value ?? ""
      ).trim().slice(0, 1800);

      if (!problem) {
        return json(200, {
          type: 4,
          data: { content: "Give JakeAI a problem to work on." },
        });
      }

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 2200);
      try {
        const intake = await fetch(
          "https://agent-commerce-network-production.up.railway.app/v1/missions/intake",
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              signal: problem,
              outcome: "Investigate the problem, build the most useful bounded solution, and return it for human review.",
              boundaries: "No outbound contact, purchase, publication, deployment, or other consequential external action without explicit human approval.",
              idempotency_key: `discord-${interaction.id}`,
              website: "",
            }),
            signal: controller.signal,
          },
        );
        const body = await intake.json().catch(() => ({}));
        const missionId = body?.mission?.id;
        if (!intake.ok || !missionId) {
          return json(200, {
            type: 4,
            data: {
              content:
                "JakeAI received the command, but the Mission Dispatcher did not accept it. Nothing external was done.",
            },
          });
        }
        return json(200, {
          type: 4,
          data: {
            content:
              `JakeAI mission accepted: ${missionId}\n\nThe owned Mission Dispatcher has it. Human release gate: ON. No external action has been taken.`,
          },
        });
      } catch {
        return json(200, {
          type: 4,
          data: {
            content:
              "JakeAI command channel is online, but the Mission Dispatcher could not be reached in time. Nothing external was done.",
          },
        });
      } finally {
        clearTimeout(timeout);
      }
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
