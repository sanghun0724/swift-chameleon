# Swift parser design decision

Choose the dedicated Swift table as the base. Two independent grammar probes agree that the generic spec alone loses inline parameters, attributes and declaration roles. The adapter candidate overrides most generic readers, so it adds a second representation without reducing implementation work.

Keep the existing walker, ParsedFile record, profile and MCP contract. Graft the adapter candidate's scoped-import cases, property attribute evidence, role eligibility and explicit unknown-history behavior into the implementation requirements. Defer full semantic history fingerprinting. The first history guarantee excludes whitespace-only and pure-rename touches; comments remain changes.

Grade candidates on extraction correctness, reuse of upstream boundaries, runtime context completeness and verifiability. Both viable candidates require runtime shape integration and role protection. The dedicated table keeps Swift grammar knowledge in one place. Independent plan review records any remaining changes in plan-review.md.
