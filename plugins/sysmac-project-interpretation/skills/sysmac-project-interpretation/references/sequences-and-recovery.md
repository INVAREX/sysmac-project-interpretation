# Sequence and recovery review

Trace a requested sequence from task entry to its observable completion. Use a transition table when it clarifies the logic: current step/state, entry guard, actions, exit guard, next state, reset/abort path, and retained data. Include each request's writer and each acknowledgement's owner.

## Useful review questions

| Area | Evidence to follow |
| --- | --- |
| Entry and scheduling | Task assignment, program ordering, Auto/Manual/startup guards, call conditions |
| Handshake | Request set/clear, receiver acknowledgement, data-valid interval, completion ownership, timeout |
| State changes | All step writers and clearing operations, mutual exclusion, same-scan transitions |
| Order/queue data | Parse buffer, matched model index, enqueue, dequeue, active flag, current-model copy, consumer reads |
| Abort and cancel | Whether requests and motion consumers stop before data is cleared; pending success versus cancel ordering |
| Restart | Retained data versus nonretained steps, stale counters, in-process material, already-acknowledged work |
| Counts | Increment/decrement event, one-shot behavior, complete/greater-than guards, reject and extra-part accounting |
| Reset and retry | Fault reset versus disposition clear, ordinary restart versus explicit retry, permissions and data lifetime |

For a concrete issue, show a short timeline with the minimum triggering conditions. For example: a load request waits for lane readiness; Auto drops in the same scan readiness becomes true; an early search consumes the queue before a later abort branch can act. Confirm the actual current guards and rung order before applying this pattern.

Other patterns recovered from the source material:

- A search can return the correct model index while later copies read an unrelated manual-entry index. Trace data provenance across each copied field.
- Publishing load completion before setting an active flag or copying required model data leaves downstream consumers with inconsistent state.
- Holding cancel for a fixed time does not establish that the sequence is idle or that outstanding work has been reconciled.
- Clearing fault bits can discard a failed part's disposition before restart selects reject versus revalidation. Establish the intended recovery contract before recommending retained flags.
- Normal-path accounting can be correct while a stop between physical release and count update creates a narrow recovery window. Treat the exact interruption window separately from general accounting.
- A program can exist without a task assignment; a newly scheduled program can still lack occupancy writers or motor-request consumers.

These are investigation prompts, not standing findings. Fixed lot sizes, reserved array rows, earliest-ready queue selection, lane numbering, and permissive behavior may be intentional. Establish the user's requirements and the current source rather than importing equipment-specific assumptions.

For external handshakes, name missing contracts. An incoming peer bit might mean “transfer accepted” or “tote physically clear”; source alone cannot resolve that distinction. Identify what local logic assumes and what protocol evidence would settle it.

Source replays should bound their scenarios and expose initial/prior-scan state. Timer completion, task preemption, physical motion, network timing, and controller power-loss behavior require additional evidence or native testing. Static assertions that named symbols are present do not establish a complete reachable sequence.
