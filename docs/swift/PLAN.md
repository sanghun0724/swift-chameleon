# SwiftChameleon implementation plan

## Goal

Provide Swift developers with repository-specific examples before AI edits. Reuse Chameleon's profile, trust, context, hook, and MCP pipelines. Keep upstream history and the MIT license. Publish this independent project to the user's confirmed private GitHub account.

## Done predicate

A fresh environment installs the pinned Swift grammar. A committed Swift fixture bootstraps a profile, distinguishes declaration roles, extracts truthful imports, type relationships, attributes and callable signatures, selects a recent substantive implementation, and returns it through pattern context and the real pre-edit hook. MCP stdio exposes the same context. Existing language tests and lint remain green. Unsupported semantic call resolution and Swift convention blocking are reported as unavailable.

## Architecture

The existing ParsedFile and ASTSignature records remain the boundary. Swift parser tables emit these records. Existing clustering and profile serialization consume them. The initial capability is extraction plus contextual guidance, not a Swift compiler or a type-resolved call graph.

Candidate A extends LanguageSpec with Swift-specific field and callback options. Candidate B supplies a dedicated Swift table implementing the existing walker contract. Select B. Both independent grammar investigations found repeated name fields, inline parameters, and declaration-kind reuse that the generic spec cannot represent truthfully. Keep Swift readers in one dedicated table.

The canonical selector receives a path-to-commit-time map. Whitespace-aware recency ignores whitespace-only diffs and follows pure renames without awarding a new timestamp. This is not semantic change detection. Comments and identifier changes still count. An unavailable or bounded-out history lookup must be explicit and conservative. Do not parse history in the pre-edit hook.

## Units

1. Ground the shipped Python pipeline and capture upstream tests before changes.
2. Compare parser designs and independently review this plan. Resolve blocking findings before implementation.
3. Add a dedicated Swift detector for SPM, Tuist and Xcode markers with actual source. Register capabilities explicitly. Keep lint detection unchanged. Add read-only Swift shape snapshots to runtime context scoring. Prevent incompatible declaration roles from being merged or selected. Add Swift grammar loading, repository detection, parser table, capability reporting, and syntax regression cases.
4. Add substantive Git history ranking with actual Git fixtures covering formatting, renames, real changes, non-Git and bounded fallback.
5. Give the plugin an independent marketplace identity. Keep internal chameleon module, command and profile names for upstream compatibility. Preserve attribution. Document installation for Claude Code and MCP use in Codex without claiming automatic Codex hooks.
6. Run a deterministic Swift product journey through bootstrap, trust, context, refresh, malformed hook payloads, and real stdio MCP. Persist reproducible verification commands.
7. Review comments and implementation independently. Fix accepted defects and rerun affected checks and the regression suite.
8. Commit, create the confirmed private repository, push and verify visibility and remote revision.

## Verification

Baseline upstream spec and canonical recency tests. Dedicated Swift syntax and detection tests. Existing unit suite and harness tests. Ruff lint and format. Swift-specific end-to-end journey uses generated public-style fixtures, never company code. Hook tests run subprocesses. MCP tests use the real stdio transport. Record failures and unrun checks separately.

## Scope limits

No sourcekit integration, whole-program dispatch resolution, SwiftUI semantic interpretation, macro expansion, or Swift-specific blocking lint in the first version. No company source or repository metadata is copied into this repository. No installation into hoian-ios or user-wide agent settings.

## Throughput

Reuse upstream records and context assembly. Keep extraction and Git ranking in separate files and work scopes. Do read-only design and review in parallel. Verify each implementation unit before layering the next.

## Review amendments

Runtime shape matching must use Swift extraction without advertising Swift lint. Existing-file protocol, extension and nominal type examples must not cross roles. New-file requests must retain path-only evidence. Verify source-heavy Swift repositories with Python helper manifests. Explicitly detect SPM Package.swift, root or bounded nested Tuist Project.swift, and Xcode project.pbxproj markers. History timeouts must not silently award fresh-clone mtime to a tracked candidate whose meaningful date is unknown. Bound history work and explain fallback.

## Accepted implementation gates

All six required amendments in plan-review.md are part of this plan. They are implementation requirements, not optional follow-up work. Register detection, grammar, table, capability and security recognition explicitly. Use one shared contextual snapshot helper without enabling Swift lint. Preserve hard Swift declaration roles through clustering and runtime witness selection. Require real source plus bounded SPM, Tuist or Xcode markers and test mixed-language precedence. Use bounded whitespace-aware history with pure-rename following and observable conservative fallback. Execute the syntax and product evidence matrix in the review, including negative trust/profile/hook cases. Build manifests must not become application witnesses. The initial release may omit Swift call edges to avoid overload guesses.

Independent review gate is satisfied by adopting these requirements. Review the resulting implementation against them again before publishing.
