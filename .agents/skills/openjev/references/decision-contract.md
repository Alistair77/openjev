# OpenJev v1 contract

Send `POST /v1/evaluate` with `state`, named `questions`, and optional `options`.

```json
{"state":"Customer was charged twice.","questions":{"route":{"type":"choice","instructions":"Which team handles this?","criteria":{"billing":"Charges or refunds","technical":"Product defects","other":"None of these"}}},"options":{"abstain_below":0.25,"top_k":3,"trace":true}}
```

Responses return the original question name under `answers`, plus the full probability distribution, confidence, abstention state, alternatives, margin, calibration metadata, request id, latency, and trace.
