<!-- PR title: #<n> <task title>   Branch: room/<n>-<slug>   Keep PRs under 400 changed lines. -->

Task: #<n>

## What and why
<!-- One or two sentences: what this PR changes and which acceptance criteria it covers. -->

## Changes
<!-- Key files / modules touched. -->
-

## How to test
<!-- Exact commands and what you should see. -->
```bash

```

## Acceptance criteria
<!-- Copy from the task and tick what is met. Explain anything not met. -->
- [ ]

## Checks
- [ ] Rebased on latest `main`
- [ ] Tests and lint of my area pass locally (`pytest backend/tests -q` / `npm run lint && npm run test -- --run && npm run build`)
- [ ] `test-writer` subagent run, then `reviewer` subagent run (verdict READY)
- [ ] Only files in my area / the task's paths changed
- [ ] API contract or `models.py` changed? → `/generated/api-contract.md` updated first + `api_change` published
- [ ] New env vars, services or commands? → `env_change` published

## Data safety (all must be true)
- [ ] No dataset files (HAR, HTML, MHTML, PNG/JPG, MP4, `*.info.json`) or anything from `data/`
- [ ] No raw tokens, cookies, `access_token` / `fbclid` / `gclid` / `clickid` values, IBANs, phone numbers or real scam domains, in code, tests, logs or this description
- [ ] Test fixtures are synthetic only (`example-scam.test`, fake IDs) and live only under `backend/tests/fixtures/**` or `frontend/src/test/fixtures/**` (the only paths the CI data-safety check allows)
- [ ] No hard-coded incident IDs or expected results
- [ ] Screenshots (if any) use mock data only
