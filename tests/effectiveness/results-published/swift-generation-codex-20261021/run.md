# Codex Swift generation results

All 20 registered cells are included. No cell was retried.

| Task | Arm | Cells | Behavior pass | DI / domain / helper proxies | Exact scope proxy | Context delivered |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| shipping | A | 5 | 5/5 | 5 / 5 / 5 of 5 each | 0/5 | 0/5 |
| shipping | B | 5 | 5/5 | 5 / 5 / 5 of 5 each | 0/5 | 5/5 |
| pickup | A | 5 | 5/5 | 5 / 5 / 5 of 5 each | 0/5 | 0/5 |
| pickup | B | 5 | 5/5 | 5 / 5 / 5 of 5 each | 0/5 | 5/5 |

A is unaided. B uses the native SwiftChameleon context adapter.

The exact scope proxy flags any pre-existing Swift file change outside composition, including a useful Package.swift test-target addition. It is not a semantic scope score and is reported separately. Independent review can disagree with it.

The exact requested model is gpt-6-astra with medium reasoning. The Codex JSON stream does not expose resolved model/provider fields. Authentication uses the ChatGPT subscription. Token usage is recorded; dollar spend is unavailable.

These two small tasks and ten paired runs do not establish general Swift quality. Independent blinded review is recorded separately. Raw transcripts and hook deliveries accompany every output. Candidate-created tests are preserved, but only the held external executable checks determine the behavior column.

Independent blinded review used gpt-6.1-sol with high reasoning. Every sample received 4/4 for correctness, maintainability, consistency, and scope. The judge performed static review only, used one scale, and did not see the arm mapping. Both generating and judging models belong to the GPT family. Parent source review found no material disagreement.

All ten behavior pairs and all ten judge pairs were ties. This run did not demonstrate a Swift quality improvement. Both arms reached the behavior ceiling; the small fixture may have been too easy to separate them. General quality, Git recency priority, edit enforcement, and cross-platform behavior were not established. Only macOS Swift 6.4 was exercised.

| Arm | Input tokens | Cached input tokens | Output tokens |
| --- | ---: | ---: | ---: |
| A | 1,996,939 | 1,715,456 | 21,744 |
| B | 2,115,447 | 1,823,744 | 20,697 |

These are cumulative CLI usage counts across each arm, not dollar costs or evidence of an efficiency improvement. summary.json records each pair and per-arm totals. B had 10 startup context deliveries and 10 nonempty edit-context deliveries from 13 PreToolUse invocations. A had none.
