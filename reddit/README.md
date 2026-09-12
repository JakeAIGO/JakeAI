# JakeAI Reddit / Devvit Release Lane

JakeAI Reddit games use a mandatory human-approval boundary.

Automation may build, test, lint, package, privately stage, and generate release evidence. It must not make a public release without explicit approval for that exact version.

## Current first game

Target: `reddit/malbot-masquerade/`

Game: **JakeAI: Malbot Masquerade — Factory Defense**

Current state: **PR QA / NOT PUBLIC**.

The game source, Devvit config, deterministic validation, PR-only QA workflow, private staging workflow, and human release-approval workflow are present on the feature branch. No workflow in this pull request performs public publication.

## Release rule

1. Merge approved game code to `main`.
2. `JakeAI Devvit Malbot Stage` performs QA and private `devvit upload` when the target game path changes.
3. Review the staged build and its immutable commit SHA.
4. Only after explicit human approval, run `JakeAI Devvit Malbot Release Approval` with the exact staged SHA, stable version, and phrase `APPROVE JAKEAI RELEASE`.
5. The approval workflow rebuilds the exact approved source and emits a release authorization receipt.
6. Public submission is still a separate deliberate action using the exact approved commit.

Any code change after approval voids the prior approval.

## Secret handling

The GitHub Actions secret is named `DEVVIT_TOKEN`. Never commit, paste into chat, place in screenshots, issues, logs, or source code.

## Required GitHub environment

Create a protected environment named `reddit-public-release` and require the owner/reviewer to approve executions that cross the public-release boundary.

## Merge gate

Do not merge until the PR QA workflow passes and the diff is reviewed for secrets, unintended permissions, external network calls, payment enablement, and any path that could publish publicly.
