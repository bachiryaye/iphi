# ADR 0024 — Free-only OpenRouter diagnostics (US-08 extension)

- Status: accepted, explicit owner request
- Date: 2026-11-18

## Context

The owner selected OpenRouter and supplied a local test key, requesting free LLMs.
The existing provider port, sanitized evidence pack, strict citation validation,
deterministic comparison/fallback and bounded admission remain authoritative.

## Decision

Add an isolated OpenRouter adapter at the fixed HTTPS chat-completions endpoint.
Accept only `openrouter/free` or an explicitly selected `:free` model. Send a zero
maximum price for prompt, completion, request and image, request strict JSON schema
support, disable plugins, and do not configure a fallback model. Provider failover
stays subject to the same zero price ceiling. Reject nonzero or missing reported
usage cost. Never route to a paid model when free capacity is unavailable.

Use the current HTTP client and the existing overall deadline, input/output/byte
limits and maximum two attempts. Preserve the selected upstream model from trusted
response metadata rather than taking its identity from generated prose. A rejected,
rate-limited or unavailable response produces the existing deterministic fallback.
No model authority, tool execution or remediation is added.

An optional `IPHI_LLM_REASONING_EFFORT` preserves model behavior by default. An
operator can explicitly select a supported effort for the chosen model. Local
verification uses `particle-ai/particle-1:free` with `none`, supported by its current
public model metadata. Never disable reasoning on a mandatory-reasoning model.
Reasoning and visible output share the existing token cap; incomplete output is
rejected rather than increasing the 20-second/2048-token maximums.

The credential stays only in the ignored local `.env`, permissions 600. Examples
contain placeholders. CI uses mock HTTP transport or the local fake provider and
never needs the owner's key. Live verification sends simulated, sanitized evidence
only, after offline adapter tests pass. Account authentication was verified with a
read-only request, without generating text or logging credentials/account details.

## Consequences

Free capacity, supported upstream models and quotas can change. The free router
selects the upstream model; persisted results identify the model reported for that
request. Free-provider data policies still apply to the bounded synthetic evidence.
No dependency, persistent schema, health or incident rule change is required.

## Verification

On 2026-11-18, a real IPHI diagnosis of a stored simulated collector outage
succeeded through `particle-ai/particle-1:free`: five retained observed facts,
1687 input tokens, 608 output tokens and 4444 ms provider latency. The adapter
accepted only the reported zero-cost response; the deterministic comparison was
persisted and monitoring still returned HTTP 200. This verifies transport, schema
and evidence references, not the semantic reliability of the model.

Earlier free-router timeout, transient HTTP failure and mandatory-reasoning token
exhaustion produced the expected deterministic fallback. No paid route or account
privacy change was used. CI covers the adapter with mock transport and never
receives the local key.

## Primary references

- [Free router](https://openrouter.ai/openrouter/free)
- [Structured output](https://openrouter.ai/docs/guides/features/structured-outputs)
- [Provider routing and maximum prices](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Reasoning controls and model capability metadata](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
