export const VERSION = '1.0.0-rc1';

const n = (v, d = 0) => Number.isFinite(Number(v)) ? Number(v) : d;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const pct = (a, b) => b === 0 ? 0 : (a / b) * 100;

export function normalizeRun(run = {}) {
  return {
    success: run.success !== false,
    total_cost_usd: n(run.total_cost_usd),
    input_tokens: n(run.input_tokens),
    output_tokens: n(run.output_tokens),
    retrieval_calls: n(run.retrieval_calls),
    retrieval_cost_usd: n(run.retrieval_cost_usd),
    tool_calls: n(run.tool_calls),
    recovery_tool_calls: n(run.recovery_tool_calls),
    latency_ms: n(run.latency_ms),
    task_score: clamp(n(run.task_score, 1), 0, 1),
    notes: String(run.notes || '')
  };
}

export function auditCompression(input = {}) {
  const baseline = normalizeRun(input.baseline);
  const candidate = normalizeRun(input.candidate);
  const policy = {
    min_net_savings_pct: n(input.policy?.min_net_savings_pct, 5),
    retrieval_increase_warn_pct: n(input.policy?.retrieval_increase_warn_pct, 50),
    quality_drop_tolerance: n(input.policy?.quality_drop_tolerance, 0.03),
    inferred_retrieval_cost_usd: n(input.policy?.inferred_retrieval_cost_usd, 0.002),
    inferred_recovery_tool_cost_usd: n(input.policy?.inferred_recovery_tool_cost_usd, 0.003)
  };

  const retrievalDelta = candidate.retrieval_calls - baseline.retrieval_calls;
  const recoveryToolDelta = candidate.recovery_tool_calls - baseline.recovery_tool_calls;
  const toolDelta = candidate.tool_calls - baseline.tool_calls;
  const tokenBaseline = baseline.input_tokens + baseline.output_tokens;
  const tokenCandidate = candidate.input_tokens + candidate.output_tokens;
  const tokenDelta = tokenCandidate - tokenBaseline;
  const rawSavings = baseline.total_cost_usd - candidate.total_cost_usd;
  const rawSavingsPct = pct(rawSavings, baseline.total_cost_usd || 1);

  const explicitRetrievalPenalty = Math.max(0, candidate.retrieval_cost_usd - baseline.retrieval_cost_usd);
  const inferredRetrievalPenalty = explicitRetrievalPenalty > 0 ? 0 : Math.max(0, retrievalDelta) * policy.inferred_retrieval_cost_usd;
  const recoveryPenalty = Math.max(0, recoveryToolDelta) * policy.inferred_recovery_tool_cost_usd;
  const reacquisitionPenalty = explicitRetrievalPenalty + inferredRetrievalPenalty + recoveryPenalty;
  const adjustedSavings = rawSavings - reacquisitionPenalty;
  const adjustedSavingsPct = pct(adjustedSavings, baseline.total_cost_usd || 1);
  const qualityDelta = candidate.task_score - baseline.task_score;
  const retrievalIncreasePct = baseline.retrieval_calls > 0
    ? pct(retrievalDelta, baseline.retrieval_calls)
    : (retrievalDelta > 0 ? 100 : 0);

  let verdict = 'net_savings_observed';
  let action = 'accept_candidate';
  let confidence = 'high';
  const reasons = [];

  if (baseline.success && !candidate.success) {
    verdict = 'compression_regression';
    action = 'reject_compression';
    reasons.push('Candidate failed while baseline succeeded.');
  } else if (qualityDelta < -policy.quality_drop_tolerance) {
    verdict = 'compression_regression';
    action = 'reject_compression';
    reasons.push(`Task quality dropped by ${Math.abs(qualityDelta).toFixed(3)} beyond tolerance.`);
  } else if (adjustedSavings <= 0) {
    verdict = retrievalDelta > 0 || recoveryToolDelta > 0 ? 'false_savings_or_regression' : 'no_economic_gain';
    action = 'reject_compression';
    reasons.push('Savings disappear after observed/inferred reacquisition work.');
  } else if (adjustedSavingsPct < policy.min_net_savings_pct) {
    verdict = 'marginal_savings';
    action = 'review_retention_policy';
    reasons.push(`Adjusted savings (${adjustedSavingsPct.toFixed(1)}%) are below the minimum threshold.`);
  } else if (retrievalIncreasePct >= policy.retrieval_increase_warn_pct || recoveryToolDelta > 0) {
    verdict = 'savings_with_reacquisition_penalty';
    action = 'review_retention_policy';
    reasons.push('Compression saves money, but it causes materially more information reacquisition.');
  } else {
    reasons.push('Candidate preserves task success/quality and retains material adjusted savings.');
  }

  if (!input.baseline || !input.candidate) confidence = 'low';
  else if (baseline.total_cost_usd === 0 || candidate.total_cost_usd === 0) confidence = 'medium';

  return {
    product: 'JakeAI Context Reacquisition Auditor',
    version: VERSION,
    verdict,
    recommended_action: action,
    confidence,
    economics: {
      baseline_cost_usd: +baseline.total_cost_usd.toFixed(6),
      candidate_cost_usd: +candidate.total_cost_usd.toFixed(6),
      raw_savings_usd: +rawSavings.toFixed(6),
      raw_savings_pct: +rawSavingsPct.toFixed(2),
      reacquisition_penalty_usd: +reacquisitionPenalty.toFixed(6),
      adjusted_savings_usd: +adjustedSavings.toFixed(6),
      adjusted_savings_pct: +adjustedSavingsPct.toFixed(2)
    },
    behavior: {
      retrieval_call_delta: retrievalDelta,
      retrieval_increase_pct: +retrievalIncreasePct.toFixed(2),
      recovery_tool_call_delta: recoveryToolDelta,
      tool_call_delta: toolDelta,
      token_delta: tokenDelta,
      latency_delta_ms: candidate.latency_ms - baseline.latency_ms,
      task_score_delta: +qualityDelta.toFixed(4)
    },
    reasons,
    policy,
    machine_summary: `${verdict}:${action}`
  };
}
