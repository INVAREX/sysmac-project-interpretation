# Ladder and symbol interpretation

## Read the network, not just the list

Observed rung JSON contains `CLs` (cells), `VLs` (vertical links), comments (`CMT`), rail metadata, and cell coordinates (`X`, `Y`). Preserve absent/default coordinates as originally stored. Cell serialization order alone does not define the branch graph. A compact view is a navigation aid; use full rung data and native viewing when geometry is unclear.

Observed cell types include `LD` contacts, `ST` coils, `F` functions, `FB` calls, and `HL` horizontal links. **`__type: ST` is a ladder coil, not evidence of a Structured Text body.** Inline ST is carried in cell `TXT` fields. Do not confuse instruction/type labels with execution language.

- Contacts can have `Not`, `Up`, `Dwn`, or related edge attributes. A falling-edge stop contact does not remain true for the duration of a held button. Include prior-scan state when reasoning about edges.
- Coil flags such as `S` and `RS` distinguish set/reset behavior from a normal output coil. Trace every set, reset, ordinary assignment, and whole-structure operation that may affect the same bit.
- Function and FB `In`/`Out` pins preserve `Arg`, `Var`, `Type`, `IO`, `Not`, and power-flow pin types. An empty `Var` may be an intentionally unconnected pin; do not treat it as a missing variable automatically.
- `IO=true` identifies potential read/write arguments. An `In` list can therefore contain an object that is mutated by a callee. Resolve the interface and callee body before deciding direction.
- Geometry, pin `Type`, and instruction metadata can change behavior. Do not delete these from a supposedly semantic comparison merely to reduce diff noise.
- Interpret same-scan effects in the actual body/task order. A step set in an earlier rung may enable later logic in the same invocation; a downstream consumer may see a new or previous value depending on execution order.

## Resolve symbols through their declarations

Build a scoped map of globals, POU locals, external variables, interfaces, UDT members, FB instances, and imported definitions. Preserve declaration types, array bounds, initial values, retention, and address/publication fields. Follow nested arrays and members one level at a time, with case-insensitive identifier matching where applicable. Dynamic indices require bounds and reachable-value analysis, not removing brackets and declaring the path valid.

For FB calls, validate named arguments against the actual function block interface and distinguish built-ins/imported types whose interface is not available. An unresolved imported type is unknown rather than proof of an invalid member. Name resolution alone does not establish correct types, units, direction, or compatible retained layouts.

## Establish writers and consumers carefully

To support an absence claim, examine:

- Direct coils and function/FB output arguments.
- In/out references and side effects inside called POUs.
- Inline ST and readable ST bodies, including indexed/indirect assignments.
- Whole-structure `MOVE`, `Clear`, copies, and resets affecting members.
- Initialization, retention, startup logic, and alternate tasks/programs.
- HMI events, mapped network data, externally writable/public variables, imported or unreadable code.

Use wording such as “no writer found in the inspected local PLC code; external writers were not supplied” when that is the actual evidence. A regex that checks direct member paths is a candidate detector and should report unresolved cases. It is not a compiler or a complete cross-reference engine.

If a source-backed Boolean replay is helpful, model only the requested branch after verifying the source geometry and instruction meanings. Stop on unsupported instructions or edge behavior. Do not implement a catch-all “unknown condition returns true”; that can make an incorrect branch appear proven. Record modeled assumptions, omitted effects, and the source hash.
