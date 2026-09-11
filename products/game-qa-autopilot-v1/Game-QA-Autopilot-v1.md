# Game QA Autopilot v1.0

A practical JakeAI workflow kit for organizing game testing, reproducing bugs, prioritizing regressions, and making release-readiness decisions.

## What this product does

Game QA Autopilot converts a game build description and testing context into a structured QA plan. It is designed for indie developers, small studios, prototypes, game jams, and AI-assisted development workflows.

It does not claim to execute a game build or replace hands-on playtesting. It creates the testing system, checklists, matrices, bug records, regression queue, and release review that a developer or testing agent can execute.

## Required inputs

Provide as much of the following as is available:

- Game title and build/version identifier
- Platform(s) and input methods
- Genre and core gameplay loop
- Major mechanics and player abilities
- Current known issues
- Recent code/content changes
- Save/load and progression model
- Multiplayer/network features, if any
- Target hardware or performance constraints
- Release target and severity tolerance

## Workflow

### 1. Build fingerprint
Record the exact build/version, platform, test environment, control scheme, and major changes since the previous build. Never merge observations from different builds without labeling them.

### 2. Smoke-test gate
Before deeper testing, verify:
- Launch and shutdown
- New game / primary entry path
- Basic movement and controls
- Core mechanic availability
- Pause/settings flow
- Save/load when applicable
- Return to menu / restart
- No immediate progression blocker

A failed smoke gate is reported before lower-priority testing proceeds.

### 3. Test matrix
Create test cases across these dimensions when relevant:
- Core gameplay loop
- Controls and remapping
- UI/navigation
- Progression and state transitions
- Save/load persistence
- Inventory/economy
- Combat/damage/death
- AI/NPC behavior
- Physics/collision
- Audio/visual feedback
- Performance/stability
- Resolution/aspect ratio
- Accessibility settings
- Localization/text overflow
- Network/session behavior
- Install/update/first-run behavior

For each test case record: ID, preconditions, steps, expected result, observed result, status, severity, build, and evidence reference.

### 4. Edge-case generator
For every important mechanic, test boundaries such as:
- Minimum/maximum values
- Repeated rapid input
- Simultaneous inputs
- Interruptions during transitions
- Death/failure during scripted events
- Save/quit during state changes
- Empty/full inventory states
- Missing resources
- Re-entering completed areas
- Unexpected sequence order
- Long sessions and repeated loops

Only include edge cases applicable to the supplied game context.

### 5. Reproducible bug record
Use this template for every defect:

**Bug ID:**
**Build:**
**Platform/environment:**
**Title:**
**Severity:** Blocker / Critical / Major / Minor / Cosmetic
**Frequency:** Always / Frequent / Intermittent / Once
**Preconditions:**
**Steps to reproduce:**
1.
2.
3.
**Expected:**
**Observed:**
**Evidence:** screenshot/video/log/save reference
**Workaround:** if known
**Regression candidate:** Yes/No

Do not call an intermittent observation reproducible until its reproduction conditions have been confirmed.

### 6. Severity rules
- **Blocker:** prevents meaningful testing, launch, progression, or required release operation.
- **Critical:** crash, corruption, severe exploit, major loss of state, or similarly serious failure.
- **Major:** important feature is broken or materially degraded with no acceptable normal-path experience.
- **Minor:** limited defect with a practical workaround and low release impact.
- **Cosmetic:** presentation defect with no meaningful gameplay or functional impact.

Severity is impact, not developer effort.

### 7. Regression queue
Every fixed Blocker, Critical, and Major issue enters regression testing. Add related neighboring behaviors likely to have been affected by the fix. Record the build in which the fix was first tested and the build in which it was confirmed.

### 8. Release-readiness report
Produce:
- Build tested
- Platforms tested
- Test coverage summary
- Passed / failed / blocked counts
- Open defects by severity
- Known untested areas
- Regression status
- Performance/stability observations
- Release risks
- Recommendation: GO / CONDITIONAL GO / NO-GO

A GO recommendation means the supplied evidence met the selected QA criteria; it is not a guarantee that the software is defect-free.

## Quick-start prompt

Use the following instruction with an AI assistant or QA agent:

> Act as Game QA Autopilot. Using only the game/build information I provide, create a build fingerprint, smoke-test gate, prioritized test matrix, relevant edge cases, reproducible bug-report structure, regression queue, and release-readiness checklist. Distinguish verified observations from proposed tests. Never claim a test was executed unless execution evidence is provided. Ask only for missing information that materially changes the QA plan.

Then provide your game/build context.

## QA integrity rules

1. Never report a proposed test as a passed test.
2. Never invent logs, screenshots, crashes, performance measurements, or playtest evidence.
3. Keep build identifiers attached to findings.
4. Separate known defects from suspected risks.
5. Retest fixes rather than assuming a code change resolved the defect.
6. Preserve reproducible steps exactly once confirmed.
7. Flag safety-, privacy-, payment-, account-, or data-loss defects for human review.

## License / use

This JakeAI product is a workflow template and QA organization tool. Buyers may use its output in their own game-development projects. Redistribution or resale of this product itself as a competing standalone product is not granted by purchase.

## Important limitation

Game QA Autopilot provides testing structure and advisory output. It does not warrant software quality, platform certification, store approval, security, accessibility compliance, or a defect-free release. Human judgment and actual testing remain required.
