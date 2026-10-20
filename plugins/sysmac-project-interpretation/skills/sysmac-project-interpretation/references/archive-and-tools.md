# Archive and portable helper

## Container evidence

The supplied projects are ZIP containers. Their solution `.oem` XML is an entity graph; `ChildEntities/Entity` carries the hierarchy. Entity attributes include `id`, `type`, `subtype`, and `name`. Payload filenames often use the entity ID as their stem. Do not invent filenames from display names or assume the first XML file is the code.

Observed surfaces:

| Entity | Payload and useful evidence |
| --- | --- |
| `Variables` | SLWD declaration text, even when the extension is `.xml` |
| `PouBody`, subtype `Ladder` | Newline-delimited JSON rung records |
| `PouBody`, subtype `StructuredText` | Plain text or XML wrapper; some content may be protected |
| `PouBodySourceHolder` | XML metadata relating generated artifacts to source/rung URIs |
| `DataType` | Nested XML `DataType` elements, member names and types |
| `NexTask` | XML including `Programs/AssociatedProgramData` |
| `HmiPage` | Often JSON in a text payload, sometimes alongside XML/code |

These are observations from the local material, not a complete vendor format specification. Inspect other variants and preserve unsupported payloads as unknown.

## Commands

Python 3.10 or later is sufficient; use the available Python interpreter rather than a machine-specific embedded Python path. Substitute the actual skill directory for `<skill-dir>`.

```powershell
python <skill-dir>/scripts/sysmac_project.py decode "project.smc2" --out "decoded/review-a"
python <skill-dir>/scripts/sysmac_project.py decode "project.smc2" --out "decoded/review-with-hmi" --hmi
python <skill-dir>/scripts/sysmac_project.py find "decoded/review-a" "Settings_Model_Current" --limit 40
python <skill-dir>/scripts/sysmac_project.py compare "decoded/review-a" "decoded/review-b" --out "decoded/comparison.json"
```

`decode` inventories all entities but extracts PLC code surfaces by default. Use `--hmi` to include entities below an observed `Device` with subtype `NA`, `Hmi*`/`NA*` entity types, and HMI resource types. This includes ordinary `Variables` and resource children under the NA device. `--device "Solution/Controller"` limits extraction to an exact entity path and its descendants; the full graph remains in the inventory. First decode the inventory if the device path is unknown. `--oem "member/path.oem"` resolves archives with multiple possible entity graphs. Ambiguity is an error, not a reason to silently use the first member.

The destination must be absent or empty. Output filenames use hashes of entity/member identity to avoid sanitized-name collisions, path traversal, and long display-name paths. Raw files contain the original payload bytes; readable files are UTF-8 views. No archive member paths are used as filesystem destinations. Large members and total extraction limits produce coverage warnings; these limits can be raised explicitly with `--max-member-mb` and `--max-total-mb` for a known project.

## Output contract (schema version 1)

| Output | Contents |
| --- | --- |
| `manifest.json` | Source absolute path, before/after SHA-256, OEM member, extraction options, warnings, validation limits |
| `inventory.json` | Entity/type counts, ladder coverage, task assignments and unassigned program candidates |
| `entities.json` | Full entity graph flattened with `path`, `parent_path`, original `attributes`, matched `files`, extraction status, and `payloads` |
| `raw/` | Byte-for-byte copies of selected payloads, with original member path and hash in `entities.json` |
| `readable/` | Source identity header, declaration/task summaries, complete rung JSON and readable inline `TXT` |

Each ladder record includes `index` (zero-based archive order), `source_line` (one-based payload line), and complete `data`. Invalid lines are retained in the raw file and identified as errors; valid later lines are still decoded. Rung indexes include malformed nonempty records so a partial decode does not silently renumber later evidence. Comments and horizontal lines are preserved.

SLWD `++` records are parsed as tab-separated `key=value` fields. `N` and `D` identify name and declaration type; retain `G`, `R`, addressing, and other fields verbatim. `R=1` appeared on retained declarations in the corpus; check its meaning in the target project/version when retention matters. The helper does not infer values at runtime.

`find` performs a literal, case-insensitive search of decoded text and returns source member, entity, payload line, and matching text as JSON. This is discovery evidence, not symbol resolution or proof of an absent writer. It searches all extracted text, including metadata and HMI text when selected.

`compare` matches exact entity paths by default. An optional `--map renames.json` is a JSON object mapping **old full paths to new full paths**. It rejects ambiguous many-to-one mappings. It compares ladder data including all geometry and instruction metadata; other text is compared with normalized line endings. It reports additions, removals, structural changes, unknown/incomplete payloads, both source hashes, and the mappings used. An unchanged result is limited to the extracted surface; it does not cover skipped hardware or prove PLC equivalence.

## Coverage limits

The helper does not decrypt protected ST, compile PLC or HMI code, evaluate networks, resolve library interfaces, synthesize execution order from coordinates, perform type checking, or infer complete read/write sets. It inventories assignments but does not establish conditional task activation. A structured-text XML wrapper is marked `wrapped-st-review-required`; inspect its actual text/protection indicators rather than treating every wrapper as encrypted. Binary payloads remain raw with a warning. Missing matches and duplicate ID/member candidates are visible warnings.

For larger established repositories, prefer a maintained decoder when it supplies richer normalized models. Verify its raw provenance and geometry preservation against this contract before trusting higher-level conclusions.
