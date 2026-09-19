import assert from "node:assert/strict";
import { normalizeIntake, detectSecrets, qualifyCase, buildDraftProposal } from "../lib/pilot-concierge-core.mjs";

const strong=normalizeIntake({
  name:"Internal Test",email:"test@example.com",company:"JakeAI",role:"Operator",
  job:"Every morning review new founding pilot requests, classify them, identify missing information, prepare a bounded scope and place the result in a human approval queue.",
  desired_outcome:"Every valid intake produces a complete review packet before human response with zero automatic customer contact and fewer missed leads.",
  tools:"JakeAI website, Netlify, approval queue",
  approval_boundaries:"Never email a customer, spend money, publish, deploy, delete data, or make a contractual commitment without human approval.",
  frequency:"On new event / message",data_sensitivity:"Ordinary business data",
  constraints_context:"Evidence-first, low-cost and human-gated."
});
const q1=qualifyCase(strong);
assert.equal(q1.risk,"low");
assert.ok(q1.score>=75);
assert.equal(q1.fit,"strong-fit");
assert.ok(buildDraftProposal(strong,q1).includes("Human approval gates"));

const sparse=normalizeIntake({
  name:"Test",email:"test@example.com",
  job:"Sometimes I need help organizing work.",
  desired_outcome:"Make it better.",
  frequency:"As needed",data_sensitivity:"Not sure"
});
const q2=qualifyCase(sparse);
assert.notEqual(q2.fit,"strong-fit");
assert.ok(q2.open_questions.length>=3);

const risky=normalizeIntake({
  name:"Test",email:"test@example.com",
  job:"Automatically purchase inventory, send payments and delete cancelled supplier accounts.",
  desired_outcome:"Complete purchasing without human delay.",
  tools:"Bank account, supplier portal, ERP, email",
  approval_boundaries:"Human approval is required for all purchases and payments.",
  frequency:"Several times a day",data_sensitivity:"Regulated / compliance-sensitive",
  constraints_context:"Audit trail required."
});
const q3=qualifyCase(risky);
assert.equal(q3.risk,"high");
assert.ok(q3.preliminary_price.setup_from>q1.preliminary_price.setup_from);

const secret=normalizeIntake({
  name:"Test",email:"test@example.com",
  job:"Use this integration.",
  desired_outcome:"Automate it.",
  tools:"api_key = abcdefghijklmnopqrstuvwxyz123456"
});
assert.equal(detectSecrets(secret),true);

console.log("Pilot Concierge core tests passed",{
  strong:{score:q1.score,fit:q1.fit,risk:q1.risk},
  sparse:{score:q2.score,fit:q2.fit,risk:q2.risk},
  risky:{score:q3.score,fit:q3.fit,risk:q3.risk}
});