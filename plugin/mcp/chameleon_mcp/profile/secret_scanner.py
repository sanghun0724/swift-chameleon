"""Secret scanner for canonical excerpts.

Phase 4 implementation: integrates `detect-secrets` (vendored, version-pinned)
with a regex-fallback when the library is unavailable.

Round 1 + Round 4 critical security mitigation. The scanner runs on every
candidate canonical file BEFORE the file is committed to `canonicals.json`.
Files with detected secrets are excluded from the canonical pool.

Per docs/architecture.md "Security mitigations" #1.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any

from chameleon_mcp.secret_placeholder import secret_value_is_placeholder

_FALLBACK_PATTERNS = (
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key"),
    (re.compile(r"\b[A-Za-z0-9/+=]{40}\b"), "possible_aws_secret"),
    (re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b"), "github_token"),
    # GitLab token family (PAT, deploy, feed, SOAT, runner). detect-secrets
    # 1.5.0 covers these too; the fallback keeps parity with the GitHub entry
    # above so GitLab tokens stay caught if detect-secrets is ever unavailable.
    (re.compile(r"\b(glpat|gldt|glft|glsoat|glrt)-[A-Za-z0-9_\-]{20,50}\b"), "gitlab_token"),
    (re.compile(r"\bsk-(ant-|proj-)?[A-Za-z0-9_\-]{20,}\b"), "ai_api_key"),
    (re.compile(r"\bsk_live_[A-Za-z0-9]{24,}\b"), "stripe_live_key"),
    (re.compile(r"\b(rk|sk)_(live|test)_[A-Za-z0-9]{24,}\b"), "stripe_key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "slack_token"),
    # Google API key: the AIza prefix is unique to Google credentials and the
    # 35-char body is fixed-length, so the shape is deterministic with little
    # room for a benign collision.
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "google_api_key"),
    # GCP service-account key files are JSON carrying this exact type marker
    # alongside a private_key. Matching the marker catches the whole file even
    # when the embedded key itself is split or base64-wrapped.
    (
        re.compile(r"""["']type["']\s*:\s*["']service_account["']"""),
        "gcp_service_account",
    ),
    # Azure Storage / Service Bus connection strings expose the shared key via
    # an AccountKey= segment terminated by ';' or end-of-string.
    (re.compile(r"\bAccountKey=[A-Za-z0-9+/=]{16,}"), "azure_account_key"),
    (re.compile(r"\b[a-f0-9]{40,}\b"), "high_entropy_hex"),
    (
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"),
        "private_key",
    ),
    (
        re.compile(
            r"""(password|passwd|pwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['"][^'"]{8,}['"]""",
            re.IGNORECASE,
        ),
        "password_assignment",
    ),
)


_NOISY_DETECT_SECRETS_TYPES = frozenset(
    {
        "Base64 High Entropy String",
        "Hex High Entropy String",
    }
)


# The two shape-only fallback patterns below match ordinary code with no
# credential context: any 40-char base64 run is a long camelCase identifier
# (e.g. adminListingNotesCreateRequestDescriptor) and any 40+ hex run is a git
# SHA or a sourcemap hash. Both are advisory-only, so on a real repo they flood
# the advisory tail without ever blocking. Keep one of their matches only when
# the line that holds it also names a credential, so a true secret assignment
# (api_token = "...") still flags while bare identifiers and hashes do not.
_CONTEXT_GATED_KINDS = frozenset({"possible_aws_secret", "high_entropy_hex"})
_SWIFT_UNINITIALIZED_PROPERTY = re.compile(
    r"\s*(?:(?:private|public|internal|fileprivate|open|static|lazy|weak|unowned)\s+)*"
    r"(?:let|var)\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*"
    r"(?P<identifier>[A-Za-z_][A-Za-z0-9_.]*\??)\s*"
)
_SWIFT_FUNCTION_DECLARATION = re.compile(
    r"\s*(?:(?:private|public|internal|fileprivate|open|static|class|final|override)\s+)*"
    r"func\s+(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\([^()'\"={}]*\)\s*\{\s*"
)
_LONG_SECRET_SHAPE = next(p for p, kind in _FALLBACK_PATTERNS if kind == "possible_aws_secret")
_SWIFT_POSSIBLE_REGEX_START = re.compile(r"(?:=|\(|\[|:|,|\breturn|\bcase)\s*/(?![/*])")


def _swift_compiler_parses(content: str) -> bool:
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["/usr/bin/xcrun", "swiftc", "-frontend", "-parse", "-"],
            input=content.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


# Credential words that open the context gate, matched as whole TOKENS rather
# than substrings. A bare alternation matched inside ordinary prose -- "auth" in
# "authored", "key" in "monkey", "access" in "accessible", "secret" in
# "secretary" -- so a sentence naming a file next to a 40-char path reported a
# leaked AWS credential. Tokenizing is the same word-boundary precision
# `classify_security_surface` already applies to paths, for the same reason.
#
# Exact-only, no prefix scheme: "auth"/"secret" as prefixes would re-admit
# "authored" and "secretary". The concatenated identifier forms a substring
# matcher used to catch (SECRETKEY, AUTHTOKEN) are therefore listed literally --
# none of them is an ordinary English word, so listing them costs no precision.
_CREDENTIAL_WORDS = frozenset(
    {
        "auth",
        "access",
        "private",
        "key",
        "keys",
        "apikey",
        "apikeys",
        "accesskey",
        "secretkey",
        "privatekey",
        "secretaccesskey",
        "token",
        "tokens",
        "authtoken",
        "accesstoken",
        "refreshtoken",
        "secret",
        "secrets",
        "apisecret",
        "password",
        "passwords",
        "passwd",
        "pwd",
        "credential",
        "credentials",
    }
)


def _credential_words_in(text: str) -> bool:
    """True when ``text`` carries a credential word as a whole token.

    camelCase boundaries split first (``apiKey`` -> ``api`` ``key``), then every
    non-alphanumeric run delimits, so ``AWS_SECRET_KEY``, ``api-key``, and
    ``{"access": ...}`` all tokenize to the credential word while ``authored``
    and ``monkey`` stay single non-credential tokens.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return any(t in _CREDENTIAL_WORDS for t in re.findall(r"[a-z0-9]+", spaced.lower()))


class IncompleteSecretScan(Exception):
    """The complete witness could not be checked by the secret scanner."""


def _try_detect_secrets(
    content: str, *, require_complete: bool = False
) -> list[dict[str, Any]] | None:
    try:
        from detect_secrets.core.scan import scan_line
        from detect_secrets.settings import default_settings
    except ImportError as exc:
        if require_complete:
            raise IncompleteSecretScan("secret scanner is unavailable") from exc
        return None

    from chameleon_mcp._thresholds import threshold_int

    # detect-secrets re-scans the whole line through its allowlist regexes for
    # every candidate it yields, so a token-dense single line (minified bundle,
    # generated const map) costs O(candidates x length) — tens of seconds at
    # 100KB. Non-strict scans leave long lines to the fallback patterns;
    # complete witness scans reject lines the backend cannot inspect.
    max_line_len = threshold_int("SECRET_SCAN_MAX_LINE_LEN")

    hits: list[dict[str, Any]] = []
    try:
        with default_settings():
            for line_no, line in enumerate(content.splitlines(), start=1):
                if len(line) > max_line_len:
                    if require_complete:
                        raise IncompleteSecretScan("line exceeds the secret scanner limit")
                    continue
                try:
                    for s in scan_line(line):
                        if s.type in _NOISY_DETECT_SECRETS_TYPES:
                            continue
                        # Compute the placeholder verdict from the EXACT flagged
                        # token here, then discard it -- the raw value is never
                        # stored (secret_value stays redacted). This lets the
                        # keyword filter judge the precise token instead of every
                        # value on the line. A real high-entropy credential is
                        # never in the placeholder set, so its verdict is False.
                        hits.append(
                            {
                                "type": s.type,
                                "line_number": line_no,
                                "secret_value": "<redacted>",
                                "value_placeholder": secret_value_is_placeholder(
                                    s.secret_value or ""
                                ),
                            }
                        )
                except Exception as exc:
                    if require_complete:
                        raise IncompleteSecretScan("secret scanner failed") from exc
                    continue
    except IncompleteSecretScan:
        raise
    except Exception as exc:
        if require_complete:
            raise IncompleteSecretScan("secret scanner failed") from exc
        return None
    return hits


def _scan_patterns(
    content: str, patterns: list[tuple[re.Pattern[str], str]] | tuple, *, swift_code: bool = False
) -> list[dict[str, Any]]:
    """Linear regex scan over ``patterns``, one hit dict per match.

    Shared machinery for the full fallback set and the hard-kind fast path.
    """
    import bisect

    hits: list[dict[str, Any]] = []
    # Resolving each hit's line with rfind/count re-scanned the whole buffer
    # per hit — O(hits x content length), a multi-hundred-ms stall on a
    # token-dense single line. One offset table + a per-line context-verdict
    # cache makes each hit O(log lines).
    line_starts = [0]
    nl = content.find("\n")
    while nl != -1:
        line_starts.append(nl + 1)
        nl = content.find("\n", nl + 1)
    context_ok_by_line: dict[int, bool] = {}
    swift_tree = None
    swift_tree_loaded = False
    swift_uncertain = None
    swift_compiler_accepted = None

    def _swift_declaration_identifier(start: int, end: int) -> bool:
        nonlocal swift_tree, swift_tree_loaded, swift_uncertain, swift_compiler_accepted
        if swift_uncertain is None:
            swift_uncertain = (
                bool(_SWIFT_POSSIBLE_REGEX_START.search(content))
                or any(
                    marker in content
                    for marker in (
                        '"""',
                        "/*",
                        "*/",
                        "#/",
                        "/#",
                        "#if",
                        "#elseif",
                        "#else",
                        "#endif",
                    )
                )
                or any(
                    '"' in line and _LONG_SECRET_SHAPE.search(line) for line in content.splitlines()
                )
            )
        if swift_uncertain:
            return False
        if not swift_tree_loaded:
            swift_tree_loaded = True
            try:
                from tree_sitter import Parser

                from chameleon_mcp.extractors.treesitter.grammars import grammar_for_path

                swift_tree = Parser(grammar_for_path("source.swift")).parse(content.encode("utf-8"))
            except Exception:
                return False
        if swift_tree is None:
            return False
        try:
            if swift_tree.root_node.has_error:
                if swift_compiler_accepted is None:
                    swift_compiler_accepted = _swift_compiler_parses(content)
                if not swift_compiler_accepted:
                    return False
            byte_start = len(content[:start].encode("utf-8"))
            byte_end = len(content[:end].encode("utf-8"))
            node = swift_tree.root_node.named_descendant_for_byte_range(byte_start, byte_end)
            if node is None or node.start_byte != byte_start or node.end_byte != byte_end:
                return False
            if node.type == "simple_identifier":
                return bool(
                    node.parent
                    and node.parent.type == "function_declaration"
                    and not node.parent.has_error
                )
            if node.type != "type_identifier":
                return False
            while node is not None and not node.has_error:
                if node.type == "property_declaration":
                    return (
                        node.child_by_field_name("value") is None
                        and node.child_by_field_name("computed_value") is None
                    )
                node = node.parent
        except Exception:
            return False
        return False

    def _line_index(position: int) -> int:
        return bisect.bisect_right(line_starts, position) - 1

    def _credential_context_at(idx: int) -> bool:
        cached = context_ok_by_line.get(idx)
        if cached is None:
            start = line_starts[idx]
            end = line_starts[idx + 1] - 1 if idx + 1 < len(line_starts) else len(content)
            cached = _credential_words_in(content[start:end])
            context_ok_by_line[idx] = cached
        return cached

    for pattern, kind in patterns:
        for match in pattern.finditer(content):
            idx = _line_index(match.start())
            if kind in _CONTEXT_GATED_KINDS and not _credential_context_at(idx):
                continue
            if swift_code and kind == "possible_aws_secret":
                start = line_starts[idx]
                end = line_starts[idx + 1] - 1 if idx + 1 < len(line_starts) else len(content)
                line = content[start:end]
                declaration = _SWIFT_UNINITIALIZED_PROPERTY.fullmatch(
                    line
                ) or _SWIFT_FUNCTION_DECLARATION.fullmatch(line)
                if (
                    declaration
                    and (
                        start + declaration.start("identifier") <= match.start()
                        and match.end() <= start + declaration.end("identifier")
                    )
                    and _swift_declaration_identifier(match.start(), match.end())
                ):
                    continue
            hits.append(
                {
                    "type": kind,
                    "position": match.start(),
                    # Also carry the line so a hard-kind secret (these are the only
                    # source of the deterministic block-eligible kinds) can be
                    # mapped into a diff hunk; ``position`` is retained for the
                    # (type, position) dedup key and any offset-based caller.
                    "line_number": idx + 1,
                    "secret_value": "<redacted>",
                }
            )
    return hits


def _fallback_scan(content: str, *, swift_code: bool = False) -> list[dict[str, Any]]:
    """Regex-based scan when detect-secrets is unavailable."""
    return _scan_patterns(content, _FALLBACK_PATTERNS, swift_code=swift_code)


# Lazily-filtered subset of _FALLBACK_PATTERNS whose kinds may hard-block.
# Resolved on first use because the kind set lives in violation_class, which
# must stay importable without pulling this module (and vice versa).
_HARD_PATTERNS: list[tuple[re.Pattern[str], str]] | None = None


def scan_for_hard_secrets(content: str) -> list[dict[str, Any]]:
    """Scan only for the deterministic hard-block secret kinds. Regex-only.

    The fast path for latency-sensitive callers (the pre-write deny, the
    corrections-exhausted block gate): never imports or runs detect-secrets,
    whose per-line allowlist re-scan is quadratic on token-dense lines. This
    loses nothing for the block decision — hard-blockable kinds only ever
    originate from the fallback patterns (detect-secrets type strings never
    parse into the deterministic kind set) — and no hard kind is context-gated,
    so the credential-keyword gate in the shared scan never filters here.
    Emits the same hit dict shape as ``_fallback_scan``.
    """
    global _HARD_PATTERNS
    if _HARD_PATTERNS is None:
        from chameleon_mcp.violation_class import _DETERMINISTIC_SECRET_KINDS

        _HARD_PATTERNS = [
            (pattern, kind)
            for pattern, kind in _FALLBACK_PATTERNS
            if kind in _DETERMINISTIC_SECRET_KINDS
        ]
    return _scan_patterns(content, _HARD_PATTERNS)


def scan_for_secrets(
    content: str, *, language: str | None = None, require_complete: bool = False
) -> list[dict[str, Any]]:
    """Return list of detected secrets in content. Empty list = safe.

    Runs BOTH detect-secrets (when available, broad coverage) AND the
    fallback regex set (deterministic, conservative). detect-secrets relies
    on entropy + context heuristics that may miss inline test fixtures or
    short example values; the fallback patterns catch those reliably.
    Hits are deduplicated by (type, position). When require_complete is true,
    an unavailable scanner or an over-limit line raises IncompleteSecretScan.
    """
    hits: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    detect_secrets_hits = _try_detect_secrets(content, require_complete=require_complete) or []
    for hit in detect_secrets_hits:
        key = (hit.get("type"), hit.get("line_number"), hit.get("position"))
        if key not in seen:
            seen.add(key)
            hits.append(hit)

    swift_code = language == "swift"
    for hit in _fallback_scan(content, swift_code=swift_code):
        key = (hit.get("type"), hit.get("position"))
        if key not in seen:
            seen.add(key)
            hits.append(hit)

    return hits
