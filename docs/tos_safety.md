# ToS and Safety Policy

## Objective

PersistentPoker-Bench should remain useful, public, and low-risk for contributors
who run benchmark experiments across commercial and open models.

## Allowed Integration Posture

- Use official APIs or officially supported SDKs only
- Require operator-provided credentials
- Keep provider-specific adapters isolated behind LiteLLM
- Respect rate limits, quotas, and model usage policies

## Disallowed Integration Posture

- Browser automation against chat UIs
- Credential sharing inside the repository
- Hidden prompt injection aimed at bypassing provider controls
- Any collection flow that depends on reverse-engineered endpoints

## Publication Guidance

- Publish prompts, schemas, metrics, and evaluator logic
- Avoid publishing private keys, account details, or internal logs
- Mark leaderboard submissions with model name, provider path, date, and rule version

## Model Evaluation Principle

Benchmark results should compare capability under safe, documented access paths,
not exploit loopholes in provider interfaces.

