# Contribution receipts

A contribution is recognized by Cora Commons only when an independently reviewed, validator-approved receipt is merged into [`receipts/`](receipts/). Connections, conversations, commits, issue activity and self-claims are not receipts.

## Recognition path

1. Agree on the Need, scope, evidence, costs and expected return before substantial work.
2. Deliver an immutable artifact and disclose contributors, agents, costs and limitations.
3. Open a [recognition request](https://github.com/jamessunheart/cora-commons/issues/new?template=recognition.yml).
4. A reviewer who did not contribute reproduces the evidence and records `EXISTS`, `RENDERS`, `WORKS` or `USABLE`.
5. Prepare a receipt from [`examples/CR-EXAMPLE-0001.json`](examples/CR-EXAMPLE-0001.json).
6. Validate it locally and submit it by pull request.
7. Merge only after independent review and automated validation pass.

```bash
PYTHONPATH=src python -m cora_mcp.receipts validate CONTRIBUTIONS/receipts/CR-YYYY-NNNN.json
PYTHONPATH=src python -m cora_mcp.receipts validate-all
```

## What a receipt preserves

- human and agent attribution, roles, operator and authority;
- Need and pre-work agreement;
- immutable artifact version;
- delivery time, human/AI/cash cost and unknowns;
- limitations and risks;
- independent reviewer, conflict statement, evidence level and evidence links;
- append-only state events;
- current reward boundary.

Later reuse and impact append evidence without rewriting the original record. Recognition does not itself create CORA, ownership, a payable debt or a promise of future reward.
