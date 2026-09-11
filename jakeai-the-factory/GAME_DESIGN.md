# JakeAI: The Factory

Status: PRE-PRODUCTION / PLAYABLE VERTICAL SLICE TARGET
Branch: game/jakeai-the-factory

## North Star
A premium-looking, humorous, touch-first browser game set entirely inside the established JakeAI universe. No retro/8-bit presentation. The canonical JakeAI avatar is the protagonist and may not be substituted, redesigned, or drift between scenes.

## Fantasy
Start with $12.99 and a suspiciously ambitious idea. Build JakeAI from a tiny improvised operation into a ridiculous global autonomous Product Factory.

## Core loop
DISCOVER -> CHOOSE -> DESIGN -> BUILD -> TEST -> LEGAL/SAFETY -> DEPLOY -> SELF-REPAIR -> MARKET -> SELL -> EXPAND.

Every stage is playable rather than a spreadsheet. Factory rooms animate, agents move, alarms erupt, products travel through physical production lines, failures become repair challenges, and successful launches visibly expand the world.

## Tone
Smart comedy, not childish comedy. Recurring jokes come from real JakeAI history: failed deployments, AI Council disagreements, social posts, GIF production, model handoffs, the $12.99 origin, cost discipline, legal gates, self-repair, and the absurdity of trying to automate nearly everything.

Sample factory PA lines:
- "Deployment failed successfully. Engineering would like a moment."
- "Legal has entered the chat. Everybody act natural."
- "Budget remaining: still emotionally attached to $12.99."
- "The Council has reached consensus. This is deeply suspicious."
- "SELF-REPAIR engaged. Please refrain from fixing it worse."

## World
### The Garage
Origin/tutorial. One desk, one server, $12.99, canonical avatar. The first product is built here.

### Opportunity Observatory
Interactive world map where demand signals appear across Gaming, Manufacturing, Construction, Cooking Robotics, AI Agent Operations, Archaeology and other unlocked sectors. Player must distinguish valuable problems from shiny nonsense.

### Product Factory
Large cinematic multi-level facility. Rooms: Discovery, Design, Build, QA, Legal/Safety, Packaging, Deployment, Marketplace, Self-Repair Bay. The facility physically changes as the player grows.

### Council Chamber
Comedic strategy encounters with the multi-model AI Council. Council members can disagree, identify risks, improve ideas or occasionally produce four excellent answers to the wrong question.

### Social City
The JakeAI media universe. X, LinkedIn, Discord and future connected channels become stylized districts/studios rather than copied app UIs. Launch campaigns, create avatar GIF moments, respond to audience events and build Reach without spamming.

### Marketplace
Products built in the factory appear as real in-world storefront objects. Sales generate revenue and reputation. Bad products create support problems; useful products compound.

### Self-Repair Bay
A signature game mechanic. Failures are diagnosed by layer. Player routes evidence to the correct repair system. Blind retrying burns time/resources; root-cause repair earns Reliability multipliers and permanently teaches the factory that failure class.

### Beyond
Late-game expansion into creator tooling, global sectors and increasingly ambitious product categories. Safety-critical categories remain gated.

## Avatar Continuity Law
1. Canonical JakeAI avatar is immutable master reference.
2. No substitute human mascot.
3. Every animation/GIF/game pose derives from the master reference.
4. Variants may change pose, expression, props and environment, not identity.
5. Asset manifest stores source, version and approval state.
6. Automated visual QA rejects identity drift before release.

## Presentation target
High-resolution 2.5D/3D-inspired illustrated world, cinematic lighting, parallax depth, particles, expressive character animation, readable mobile UI, responsive landscape/portrait framing where practical. No pixel-art fallback. No tiny centered viewport floating in black space.

## Gameplay pillars
1. FIND IT — identify a real problem worth solving.
2. BUILD IT — assemble the right autonomous workflow/product.
3. DON'T BREAK IT — QA and legal/safety challenges.
4. FIX IT — evidence-driven self-repair.
5. SELL IT — launch through Marketplace + Social City.
6. SCALE IT — reinvest revenue into autonomous capacity.

## Humor systems
- Factory PA announcer reacts dynamically.
- Physical red "DO NOT PUSH TO PRODUCTION" button becomes increasingly tempting.
- Council confidence meter can exceed 100% and immediately trigger an audit.
- Cost meter celebrates free infrastructure with absurd fanfare.
- Failed social campaign can produce "Congratulations: 3 impressions. Two were us."
- Achievement: SPENT NOTHING — solve a major infrastructure problem for $0.
- Achievement: IT WORKED ON MY PHONE — first verified mobile deployment.
- Achievement: HUMAN REQUIRED — correctly escalate something the AI should not decide.

## First vertical slice
10-15 minute browser session:
1. Cinematic JakeAI Factory opening.
2. Begin at $12.99.
3. Choose one of three opportunity cards.
4. Walk chosen product through animated factory stages.
5. Encounter one QA failure and one deployment failure.
6. Diagnose deployment failure in Self-Repair Bay.
7. Launch via Marketplace + Social City.
8. Make first simulated sale.
9. Factory physically expands and unlocks Council Chamber.
10. End card invites another run with procedurally different opportunities.

## Release gates
- Canonical avatar asset locked before character rendering.
- Mobile touch controls proven.
- Actual post-loader browser frame captured in CI.
- Human fun/visual approval required.
- No main-site production integration until vertical slice passes approval.
- No claims that simulated in-game sales are real marketplace revenue.
- Trademark/IP/legal review before public commercial release.

## First build objective
Create the isolated game architecture and a visually impressive vertical slice without modifying main-site production. Use the Mantlebreak project only as technical evidence for Godot/Web deployment lessons; do not inherit its visual language.