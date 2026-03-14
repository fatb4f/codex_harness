#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest_path="${1:-$repo_root/project.manifest.json}"
git_root="$(git -C "$repo_root" rev-parse --show-toplevel)"

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required" >&2
  exit 1
fi

if [[ ! -f "$manifest_path" ]]; then
  echo "manifest not found: $manifest_path" >&2
  exit 1
fi

if [[ "$git_root" != "$repo_root" ]]; then
  echo "build_overrides.sh must live at the git root" >&2
  exit 1
fi

write_if_changed() {
  local target="$1"
  local temp="$2"
  mkdir -p "$(dirname "$target")"
  if [[ -f "$target" ]] && cmp -s "$temp" "$target"; then
    rm -f "$temp"
    return 0
  fi
  mv "$temp" "$target"
}

require_manifest_string() {
  local query="$1"
  jq -er "$query | select(type == \"string\" and length > 0)" "$manifest_path"
}

require_repo_relative_path() {
  local label="$1"
  local value="$2"
  case "$value" in
    ""|/*|~*|..|../*|*/../*|*/..|*//*) 
      echo "manifest path must be relative to git_root: $label=$value" >&2
      exit 1
      ;;
  esac
}

validate_manifest_paths() {
  local root_path
  root_path="$(require_manifest_string '.paths.root')"
  if [[ "$root_path" != "." ]]; then
    echo "paths.root must be '.' to denote git_root: $root_path" >&2
    exit 1
  fi

  while IFS=$'\t' read -r label value; do
    [[ -n "$label" ]] || continue
    require_repo_relative_path "$label" "$value"
  done < <(
    {
      jq -r '.paths | to_entries[] | "paths.\(.key)\t\(.value)"' "$manifest_path"
      jq -r '
        .schema_contract
        | to_entries[]
        | select(.key == "generic_base_schema" or .key == "project_profile_schema" or .key == "compatibility_schema" or .key == "project_template")
        | "schema_contract.\(.key)\t\(.value)"
      ' "$manifest_path"
      jq -r '.priority_files[] | "priority_files[]\t\(.)"' "$manifest_path"
      jq -r '.scaffold.generated_files[] | "scaffold.generated_files[]\t\(.)"' "$manifest_path"
    }
  )
}

validate_manifest_paths

project_id="$(require_manifest_string '.project_id')"
build_script_path="$(require_manifest_string '.paths.build_script')"
generic_base_schema="$(require_manifest_string '.schema_contract.generic_base_schema')"
project_profile_schema="$(require_manifest_string '.schema_contract.project_profile_schema')"
compatibility_schema="$(require_manifest_string '.schema_contract.compatibility_schema')"
project_template="$(require_manifest_string '.schema_contract.project_template')"
profile_schema_id="$(require_manifest_string '.schema_contract.profile_schema_id')"
compatibility_schema_id="$(require_manifest_string '.schema_contract.compatibility_schema_id')"
profile_title="$(require_manifest_string '.schema_contract.profile_title')"
review_kind="$(require_manifest_string '.schema_contract.project_review_kind')"
artifact_name_pattern="$(require_manifest_string '.schema_contract.artifact_name_pattern')"
review_templates_path="$(require_manifest_string '.paths.review_templates')"
full_instructions_file="$(require_manifest_string '.paths.review_instructions')"
agents_path="$repo_root/AGENTS.md"

profile_schema_tmp="$(mktemp)"
jq -n \
  --arg schema "https://json-schema.org/draft/2020-12/schema" \
  --arg id "$profile_schema_id" \
  --arg title "$profile_title" \
  --arg base_ref "./$(basename "$generic_base_schema")" \
  --arg kind "$review_kind" \
  --arg artifact_name_pattern "$artifact_name_pattern" \
  '{
    "$schema": $schema,
    "$id": $id,
    "title": $title,
    "allOf": [
      {
        "$ref": $base_ref
      },
      {
        "type": "object",
        "properties": {
          "artifact_review": {
            "type": "object",
            "properties": {
              "kind": {
                "const": $kind
              },
              "metadata": {
                "type": "object",
                "properties": {
                  "artifact_name": {
                    "pattern": $artifact_name_pattern
                  }
                }
              }
            }
          }
        }
      }
    ]
  }' >"$profile_schema_tmp"
write_if_changed "$repo_root/$project_profile_schema" "$profile_schema_tmp"

compat_schema_tmp="$(mktemp)"
jq -n \
  --arg schema "https://json-schema.org/draft/2020-12/schema" \
  --arg id "$compatibility_schema_id" \
  --arg ref "./$(basename "$project_profile_schema")" \
  '{
    "$schema": $schema,
    "$id": $id,
    "$ref": $ref
  }' >"$compat_schema_tmp"
write_if_changed "$repo_root/$compatibility_schema" "$compat_schema_tmp"

template_tmp="$(mktemp)"
jq '.review_template' "$manifest_path" >"$template_tmp"
write_if_changed "$repo_root/$project_template" "$template_tmp"

agents_tmp="$(mktemp)"
{
  echo "# AGENTS"
  echo
  echo "This file is scaffolded from [project.manifest.json](./project.manifest.json) by [build_overrides.sh](./$build_script_path)."
  echo
  echo "Read [project.manifest.json](./project.manifest.json) first before doing review, runtime, schema, or planning work in this repo."
  echo
  echo "Use [$(basename "$full_instructions_file")](./$full_instructions_file) for the full review workflow and output contract."
  echo
  echo "Regenerate scaffolded files with [build_overrides.sh](./$build_script_path)."
  echo
  echo "## Required behavior"
  echo
  jq -r '.agent_contract.required_behavior[]' "$manifest_path" | while IFS= read -r line; do
    printf -- '- %s\n' "$line"
  done
  echo
  echo "## Review contract"
  echo
  echo "Use these files:"
  echo
  printf -- '- [%s](./project.manifest.json)\n' "project.manifest.json"
  printf -- '- [%s](./%s)\n' "$(basename "$generic_base_schema")" "$generic_base_schema"
  printf -- '- [%s](./%s)\n' "$(basename "$project_profile_schema")" "$project_profile_schema"
  printf -- '- [%s](./%s)\n' "$(basename "$compatibility_schema")" "$compatibility_schema"
  printf -- '- [%s](./%s)\n' "$(basename "$project_template")" "$project_template"
  echo
  echo "Template root: \`$review_templates_path\`"
  echo "Project id: \`$project_id\`"
  echo
  echo "If there is any conflict between ad hoc assumptions and the manifest, follow the manifest."
} >"$agents_tmp"
write_if_changed "$agents_path" "$agents_tmp"

echo "Scaffolded:"
printf '  %s\n' \
  "$agents_path" \
  "$repo_root/$project_profile_schema" \
  "$repo_root/$compatibility_schema" \
  "$repo_root/$project_template"
