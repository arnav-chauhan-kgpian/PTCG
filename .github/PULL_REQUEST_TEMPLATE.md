## What
<!-- One sentence on what this PR does. -->

## Why
<!-- The bug it fixes / the user need it serves / the audit finding it closes. -->

## How
<!-- 1-3 bullets on the approach. -->

## Verification
- [ ] `ruff check src tests` passes
- [ ] `pytest -q` passes
- [ ] Manually exercised the changed code path (describe how)
- [ ] If the change touches the FastAPI server: tested `/health`, `/move` end-to-end
- [ ] If the change touches the frontend: `npm run typecheck && npm run lint && npm run build` passes

## Notes for reviewers
<!-- Anything non-obvious; trade-offs considered; follow-up work created. -->
