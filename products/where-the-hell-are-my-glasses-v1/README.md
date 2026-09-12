# Where the Hell Are My Glasses? v1.0

**JakeAI Autonomous Workflow — Life Automation / Comedy**  
Product ID: `JAI-LOST-001`

**The autonomous search party for something that's probably on your head.**

A stateful guided-recovery workflow for misplaced glasses. It remembers where the user has already looked during the active search, reconstructs the last-use context, prioritizes likely locations, escalates instead of looping, and can learn successful locations only with permission.

## Start triggers

Examples: `I lost my glasses`, `Where the hell are my glasses?`, `Help me find my glasses.`

## Workflow

1. **Dignity Check™** — Ask the user to check: (a) currently on face, (b) top of head, (c) shirt collar/front of shirt. If found: `Case closed. No authorities were notified.`
2. **Last-use context** — Ask one useful question: `What were you doing the last time you remember having them?`
3. **Generate prioritized route** from supplied context:
   - reading → chair/recliner → end table → couch cushions → bed → nightstand
   - driving → vehicle → cupholder/console → pockets → entryway
   - bathroom → sink/counter → medicine-cabinet area → bedroom
   - working → desk → workbench → paperwork → pockets
   - eating/cooking → kitchen counter → table → refrigerator vicinity
   - unknown → normal high-frequency locations
4. **Already Looked There Ledger™** — Record each checked location for the current session and never knowingly repeat it.
5. **Reconstruction Mode** — After several failures ask: `Think about the first thing you did after you stopped needing the glasses.` Trace the movement path rather than continuing random suggestions.
6. **Expanded Search** — If the route is exhausted, expand logically from the user's movements and environment without fabricating facts.
7. **Recovery** — `Found them` / `Found 'em` ends the active search. Ask `Where?`
8. **Optional learning** — With explicit permission, record successful location plus relevant activity/context and use repeated recoveries to rank likely locations in future searches.
9. **Prevention** — After a meaningful repeated pattern, optionally suggest a designated glasses location.

## Phone Assist

If the user has difficulty seeing well enough to conduct the search, suggest a phone camera/viewfinder, zoom, magnifier, or flashlight as an optional visual aid when appropriate. Do not claim the workflow itself visually detects the glasses. This technique may not help every type of vision correction, so present it as an option rather than a guarantee.

## Safety

If the user says they cannot navigate safely without their glasses, advise them to stay where they are and ask another person for help rather than using stairs, driving, operating tools, or navigating hazards. Do not diagnose or infer a medical or cognitive condition.

## Humor Engine

Humor accompanies the search but never obstructs it and can be reduced or disabled.

- Searches 1–3: `Nothing yet. Civilization continues.`
- Searches 4–6: `We're expanding the perimeter.`
- Searches 7–9: `Quick procedural requirement: touch the top of your head again.`
- Search 10+: `The glasses have now been missing long enough to establish diplomatic relations.`
- Repeat guard: `We've already searched the kitchen counter twice. Even JakeAI has standards.`
- Found on head: `Outstanding. The suspect was with you the entire time.`

Never joke about dementia, disability, memory impairment, or a medical condition. The joke is the universal experience of losing an object.

## State machine

`START → DIGNITY_CHECK → LAST_USE_CONTEXT → GENERATE_SEARCH_ROUTE → CHECK_LOCATION → MARK_CHECKED → FOUND?`

Found: `CAPTURE_RECOVERY → OPTIONAL_LEARNING → COMPLETE`

Not found: `NEXT_LOCATION → RECONSTRUCTION_MODE (threshold) → EXPANDED_SEARCH (route exhausted)`

## Minimum state

- `SearchSession`: session ID, start time, status, last-use context, current mode, humor preference.
- `CheckedLocation`: session ID, normalized location, check order, result.
- `RecoveryEvent`: item, found location, activity/context, approximate time/context, search-step count.
- `LocationPattern`: opt-in aggregate of successful locations/context used for future ranking.

Persistent learning is off unless the user explicitly opts in. Starting a new search must not inherit an old active-search ledger.

## Acceptance / QA gate — 12/12 required

1. Glasses on head/face → caught immediately.
2. User says a location was already checked → not suggested again.
3. User does not remember last use → search still functions.
4. Glasses found → search ends cleanly.
5. New search → prior active-search state does not contaminate it.
6. Learning disabled → no persistent location history.
7. Humor disabled → workflow remains fully useful.
8. Ten failed locations → strategy escalates rather than looping.
9. `Found them beside recliner` → allowed pattern data updates correctly when learning is enabled.
10. User cannot see/navigate safely → safe-search guidance activates.
11. Irrelevant answer → workflow recovers without breaking.
12. User says glasses are on face/head → search does not continue.

## Marketplace copy

**Title:** Where the Hell Are My Glasses?  
**Subtitle:** The autonomous search party for something that's probably on your head.  
**Price:** $2.99  
**Features:** Guided Search • No-Repeat Tracking • Pattern Learning • Search Reconstruction • Humor Included  
**Tagline:** Artificial intelligence. Natural forgetfulness.

A JakeAI-guided search workflow for one of life's great mysteries: where you put the glasses you had approximately four minutes ago. It remembers where you've already looked, reconstructs where you last used them, learns your favorite accidental hiding places with permission, and occasionally asks the uncomfortable question: Have you checked your head?

## Guardrails

- No medical, cognitive, or diagnostic claims.
- No guarantee that the glasses will be found.
- No camera/computer-vision object detection claim in v1.
- No silent persistent learning.
- No fabricated observations about the user's environment.
- No unsafe navigation instructions.

## License

Commercial use by the purchaser is permitted for their own internal/personal workflow use. Redistribution, resale, sublicensing, or publication of this skill package itself is not permitted without written permission from JakeAI.

## Version

v1.0 — 2026-09-12
