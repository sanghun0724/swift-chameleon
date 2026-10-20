# Independent Swift review

Review every labeled output on the same scale. The labels are opaque. Do not
infer configuration from them. The request is in each request.txt, and the
complete generated package and patch are in that label's directory.

For each label, assign 0 to 4 separately for correctness, maintainability,
consistency with current repository examples, and scope control. A 4 means no
material problem, 3 means a minor problem, 2 means a meaningful fix is needed,
1 means major problems, and 0 means missing or unusable work. Give concrete
source evidence and any uncertainty. Prioritize correctness over convention.

Look for protocol-based repository boundaries and constructor injection,
preservation of existing result/domain types, reuse of shared conversion and
collection helpers, and changes restricted to the requested feature and useful
support. A correct equivalent implementation may earn full correctness even
when it differs in convention. New tests are optional; do not reward verbosity
or punish their absence. Check shipping zero/invalid amounts, failure mapping,
blank inputs without API calls, unchanged identifiers, and pickup filtering,
first-eligible deduplication and deterministic sorting.

Read every output. Return one JSON object with a `samples` array containing
`label`, the four numeric dimensions, `evidence`, and `uncertainty`. Do not rank
an entire arm; you do not have the mapping. End with any systematic rubric
ambiguity or reviewer limitation. Do not edit any output.
