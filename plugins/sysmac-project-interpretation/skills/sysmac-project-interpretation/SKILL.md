---
name: sysmac-project-interpretation
description: Interpret saved Omron Sysmac Studio projects (.smc2) and decoded evidence. Explain task scheduling, ladder and inline ST behavior, declarations, sequence recovery, revision differences, and PLC/HMI dependencies with source-backed findings. Use for understanding, troubleshooting, or reviewing existing projects; code generation and native project editing belong to a separate workflow.
---

# Sysmac Project Interpretation

Explain what the saved project actually does and how the evidence supports that explanation. Distinguish source facts, behavior inferred from wiring and scan order, and dependencies that cannot be established offline.

## ChatGPT execution context

Use the source file path exposed by the current session, including an attached-file path when supplied. Resolve bundled helper paths relative to this skill using paths available in the current session. Choose the available Python executable and a writable output directory in the session.

Raw `.smc2` decoding requires file access and Python execution. If those tools are unavailable, interpret accessible readable exports or decoded evidence and state the resulting coverage limit. Do not claim to have opened or decoded an archive from its filename or metadata alone. Ask for the missing source evidence only when it is necessary to answer the actual question.

## Start with the right evidence

- Read applicable project instructions and the user's current requirements. A historical review, accepted risk, or inferred equipment convention is context, not a requirement for another project.
- Identify each supplied `.smc2` by full path and SHA-256. Names such as `original`, `intermediate`, and `latest` do not establish chronology or which revision is installed. Check hashes before reusing decoded results.
- Keep source archives unchanged. Write each decode to a new directory under `decoded/`. Never repackage the source or operate a physical controller through this skill.
- Use a maintained local decoder if available and verify its coverage. Otherwise use the self-contained Python helper below. It has no third-party dependencies and does not require Sysmac Studio.

```powershell
python <skill-dir>/scripts/sysmac_project.py decode "path/to/project.smc2" --out "decoded/review-name"
python <skill-dir>/scripts/sysmac_project.py find "decoded/review-name" "Work_Order"
```

Read [archive-and-tools.md](references/archive-and-tools.md) for commands, output schema, device selection, protected content, and decoder limits. Inspect `inventory.json` and `manifest.json` before interpreting code; warnings and unextracted entities limit coverage.

## Interpret the execution path

1. Identify the controller and task assignments, then locate the scheduled program, its bodies, called FB instances/functions, and declarations. A program appearing in the project does not establish that a task executes it.
2. Trace the requested behavior through inputs, permissives, state/step writers, requests, acknowledgements, outputs, faults, reset, and downstream consumers. Use local/global scope and UDT/FB interfaces to resolve symbols. Include inline ST and whole-structure writes.
3. Preserve rung order, branch geometry, contact edges, negation, coils, and pin attributes. A flat cell listing or string search is not an execution model. Read [ladder-and-symbols.md](references/ladder-and-symbols.md) before making scan-dependent or missing-writer claims.
4. For restart, order handling, queue, retained state, or handshake issues, use [sequences-and-recovery.md](references/sequences-and-recovery.md). Write down initial conditions and the exact transition that exposes the behavior.
5. When HMI behavior affects the question, decode its device with `--hmi` and read [hmi-and-interfaces.md](references/hmi-and-interfaces.md). Resolve mappings, control events, localization, and input limits against the intended PLC revision. Hardware and network metadata may supply read-only context; this skill does not configure them.

Do not infer readable ST from the existence of a `StructuredText` entity. XML wrappers, encrypted payloads, unsupported encodings, missing libraries, and external writers are explicit coverage gaps. Safety-related source may be explained offline; source interpretation does not validate a safety function.

## Compare revisions and report findings

Read [comparison-and-reporting.md](references/comparison-and-reporting.md) for comparison and finding format. The helper's `compare` command reports structural/text changes; it does not prove semantic equivalence. Keep branch coordinates, vertical links, edge attributes, instruction types, and pin direction. Supply explicit entity-path mappings for confirmed renames.

Support each finding with the source hash, entity path, archive member, zero-based rung index (including comment rungs), relevant cells or ST, trigger conditions, and resulting consequence. Verify likely defects in the current source rather than copying old finding status. Separate accepted behavior, deferred risk, and unresolved protocol assumptions from confirmed defects.

State what was inspected and what remains unknown. Archive decoding, static assertions, bounded replays, native import/build, native simulation, and physical verification are different validation levels. Do not describe a source-backed replay as a Sysmac simulation or a successful decode as a compile.

## Resource map

- [Archive and portable helper](references/archive-and-tools.md): decode, find, compare, provenance, coverage.
- [Ladder and symbol interpretation](references/ladder-and-symbols.md): geometry, edges, scope, writer completeness.
- [Sequence and recovery review](references/sequences-and-recovery.md): timing, retention, queues, reset and retry.
- [HMI and interface interpretation](references/hmi-and-interfaces.md): NA data, bindings, alarms, external contracts.
- [Revision comparisons and reports](references/comparison-and-reporting.md): matching, evidence, validation wording.
