# Revision comparisons and reports

## Establish identity before comparing

Record source paths, full SHA-256 values, intended roles, and what the user says is current or proposed. OEM timestamps, directory dates, filenames, and a shorter hash in a review title are navigation clues. Recompute full hashes; a same-named archive may have been replaced after an older decode.

Compare relevant surfaces together: task assignments, scheduled programs, POU interfaces/locals, globals, UDTs, ladder networks, readable/inline ST, retained data shape, HMI bindings/events/limits/alarms, and dependencies of added code. Separate program existence from scheduling and integration.

Entity IDs can change between revisions. Match stable full paths first and use an explicit rename map after inspecting both sides. Avoid a universal `SEQ_` to `Sequence_` substitution: an unrelated entity can collide. The helper reports full-path differences until mappings are supplied.

For ladder, a structural comparison retains `VLs`, coordinates, order, instruction types, edge/negation flags, and pin metadata. Cosmetic metadata may produce noise, but deleting these fields can erase real wiring differences. Use a second presentation-only view if useful and describe what it ignores. Never label that reduced view semantic equivalence.

## Finding contract

Use as much detail as the request needs. For an actionable finding, preserve:

| Field | Meaning |
| --- | --- |
| Status | Confirmed defect, inference, verification question, intentional behavior, accepted/deferred risk, or withdrawn |
| Evidence | Revision hash, entity path, archive member, zero-based rung(s), cells/pins/inline ST or declaration |
| Trigger | Initial conditions and event/scan transition required |
| Behavior | What the saved source does and what observable consequence follows |
| Requirement | The user requirement or source contract that makes this a defect |
| Correction direction | Smallest coherent behavior change, if requested |
| Validation | Checks actually performed, assumptions, and checks still needed |

Prefer a concrete trigger and effect over generic warnings. Trace callers and consumers so that a locally plausible issue is not incorrectly presented as a machine-level failure. When evidence overturns a previous finding, explicitly withdraw or narrow it and explain the decisive source fact.

Carry accepted risks only when the user's current context establishes they apply. A workaround accepted for one historical revision does not authorize a different change. Preserve distinctions among fixed, open, deferred, disregarded by the user, and unresolved external contracts.

## Validation vocabulary

- **Decoded:** container/entity/payload parsing succeeded to the reported coverage.
- **Static source checked:** declarations, references, branches, or transitions were inspected/asserted.
- **Bounded replay:** a limited model exercised named scenarios with recorded assumptions.
- **Native build/compile:** actually performed in the relevant Sysmac/NA environment with results recorded.
- **Native simulation/runtime/hardware verification:** only claim the exact environment and behavior actually exercised.

No clean symbol audit or fixed number of assertions substitutes for compile, full simulation, retained-data migration checks, or engineer verification. At delivery, summarize the inspected scope, principal behavior/findings, evidence links, and material unknowns. Link the new decode's relative paths; old absolute Windows paths in archived reviews are historical references.
