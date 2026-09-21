---
name: openjev
description: Use OpenJev to turn classification, scoring, binary judgment, routing, or ranking tasks into typed, inspectable decisions. Do not use it for open-ended content generation.
metadata:
  short-description: Design and run inspectable AI decisions with OpenJev
---

# OpenJev

Use OpenJev when software needs a constrained decision it can inspect and act on. Prefer it when the output must be a fixed choice, an ordered score, or a probability for a specific statement.

## Choose the right shape

- Use `choice` for one answer from a named option set.
- Use `score` for one dimension expressed as ordered, descriptive levels.
- Use `noul` for the probability that one specific statement is supported.
- Do not use OpenJev for drafting prose, answering broad research questions, or replacing a policy owner.

## Design the decision

1. Reduce a broad question to atomic dimensions. Ask one question per dimension, then combine results in code.
2. Describe every choice or score level in concrete terms. Add `other` when the available choices may not cover the input.
3. Send all related questions against the same state in one request.
4. Use `confidence`, the full distribution, and `abstained`, not only the selected answer.
5. Preserve the response trace whenever a later reviewer may need to understand a decision.

Read [question design](references/question-design.md) before designing a new production taxonomy. Read [safety and abstention](references/safety-and-abstention.md) before connecting a decision to an external action. Read [the decision contract](references/decision-contract.md) when constructing an API call.

## Safety boundary

An OpenJev decision does not authorize destructive, financial, medical, legal, employment, or security-sensitive action. Apply an explicit policy, verification step, and appropriate human review outside the model.
