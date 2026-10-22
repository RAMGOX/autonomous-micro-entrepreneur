# Solution: [BOUNTY $50] SKILL: Generate a structured CHANGELOG from git history
- **Issue:** [claude-builders-bounty/claude-builders-bounty #1](https://github.com/claude-builders-bounty/claude-builders-bounty/issues/1)
- **Bounty:** $50 USD (powered by Opire)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Skill Definition (`.claude/skills/generate-changelog/SKILL.md`)

```yaml
---
name: generate-changelog
description: Automatically generates a Keep-a-Changelog compliant CHANGELOG.md from git commit history since the latest tag.
triggers:
  - "/generate-changelog"
  - "generate changelog"
---

Run `scripts/changelog.sh` to extract and categorize all commits since the most recent git tag into Added, Fixed, Changed, and Removed sections, then prepend to `CHANGELOG.md`.
```

---

## 2. Shell Generator Script (`scripts/changelog.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

TARGET_FILE="${1:-CHANGELOG.md}"
DATE="$(date +%Y-%m-%d)"
LATEST_TAG="$(git describe --tags --abbrev=0 2>/dev/null || echo "")"

if [[ -n "${LATEST_TAG}" ]]; then
    RANGE="${LATEST_TAG}..HEAD"
    VERSION_TITLE="## [Unreleased] - ${DATE} (since ${LATEST_TAG})"
else
    RANGE="HEAD"
    VERSION_TITLE="## [1.0.0] - ${DATE}"
fi

ADDED=()
FIXED=()
CHANGED=()
REMOVED=()

while IFS= read -r commit_line; do
    [[ -z "${commit_line}" ]] && continue
    hash="$(echo "${commit_line}" | cut -d' ' -f1)"
    msg="$(echo "${commit_line}" | cut -d' ' -f2-)"

    case "${msg}" in
        feat*|Feat*|add*|Add*)
            clean_msg="$(echo "${msg}" | sed -E 's/^[a-zA-Z]+(\([^\)]+\))?:\s*//')"
            ADDED+=("- ${clean_msg} (${hash})")
            ;;
        fix*|Fix*|bug*|Bug*)
            clean_msg="$(echo "${msg}" | sed -E 's/^[a-zA-Z]+(\([^\)]+\))?:\s*//')"
            FIXED+=("- ${clean_msg} (${hash})")
            ;;
        revert*|remove*|Remove*)
            clean_msg="$(echo "${msg}" | sed -E 's/^[a-zA-Z]+(\([^\)]+\))?:\s*//')"
            REMOVED+=("- ${clean_msg} (${hash})")
            ;;
        *)
            clean_msg="$(echo "${msg}" | sed -E 's/^[a-zA-Z]+(\([^\)]+\))?:\s*//')"
            CHANGED+=("- ${clean_msg} (${hash})")
            ;;
    esac
done < <(git log "${RANGE}" --oneline --no-merges)

TEMP_LOG="$(mktemp)"
{
    echo "${VERSION_TITLE}"
    echo ""
    if [[ ${#ADDED[@]} -gt 0 ]]; then
        echo "### Added"
        printf '%s\n' "${ADDED[@]}"
        echo ""
    fi
    if [[ ${#FIXED[@]} -gt 0 ]]; then
        echo "### Fixed"
        printf '%s\n' "${FIXED[@]}"
        echo ""
    fi
    if [[ ${#CHANGED[@]} -gt 0 ]]; then
        echo "### Changed"
        printf '%s\n' "${CHANGED[@]}"
        echo ""
    fi
    if [[ ${#REMOVED[@]} -gt 0 ]]; then
        echo "### Removed"
        printf '%s\n' "${REMOVED[@]}"
        echo ""
    fi
} > "${TEMP_LOG}"

if [[ -f "${TARGET_FILE}" ]]; then
    cat "${TARGET_FILE}" >> "${TEMP_LOG}"
fi
mv "${TEMP_LOG}" "${TARGET_FILE}"

echo "Updated ${TARGET_FILE} successfully."
```

---

## 3. Quickstart Guide (3 Steps)
1. Copy `scripts/changelog.sh` into your project and make it executable: `chmod +x scripts/changelog.sh`.
2. Run `bash scripts/changelog.sh` (or trigger `/generate-changelog` via Claude Code).
3. Review your newly structured `CHANGELOG.md` commit updates.
