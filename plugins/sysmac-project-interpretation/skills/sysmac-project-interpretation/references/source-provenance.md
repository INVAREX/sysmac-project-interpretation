# Source provenance

This skill was distilled from offline Sysmac project interpretation and revision-review workflows. Its instructions retain the reusable format observations, source-tracing practices, ladder geometry handling, sequence/recovery analysis, HMI mapping checks, and validation distinctions.

The original machine projects, historical reviews, decoded machine data, and project-specific scripts are not included and are not required to use the plugin. The helper tests use synthetic fixtures.

The reviewed material established the observed OEM entity graph, ID-based payload lookup, SLWD declarations, NDJSON ladder records, inline ST, task assignment XML, and NA HMI resource forms. These observations are not a complete vendor format specification. Unsupported payloads and content protection remain explicit coverage gaps.

Machine-specific defect IDs, accepted risks, lane ranges, lot sizes, project names, and historical findings are not standing rules. Apply the current user's requirements and inspect the current source hashes.

The comparison helper retains geometry, instruction types, and pin attributes; it does not reproduce historical comparison shortcuts that discarded those fields. Offline source checks and bounded replays are not native Sysmac compilation or physical controller verification.
