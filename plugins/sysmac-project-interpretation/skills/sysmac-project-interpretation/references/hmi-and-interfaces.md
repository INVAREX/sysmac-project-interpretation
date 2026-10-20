# HMI and interface interpretation

Read HMI source when the requested behavior depends on a screen, operator action, alarm, recipe entry, or upgrade compatibility. HMI and PLC revisions must be identified independently. The supplied material demonstrated that the live HMI and an adapted target HMI can have very different compatibility even when their names are similar.

## Trace the binding chain

1. Inventory the HMI device, variables/mapping, pages, subroutines/code, localization resources, and alarms.
2. Resolve an HMI variable's `Address` through its device mapping into the intended PLC global/instance. Do not strip a hard-coded controller prefix without checking the selected device.
3. Follow nested PLC members and array dimensions through declarations. Check aliases, dynamic expressions, and VB-style index syntax separately; regex tokenization alone does not prove expression validity.
4. Inspect the control's events and enable/visibility conditions. A button label does not establish which bit its event sets or whether it is momentary, toggled, reset, or acted upon in a subroutine.
5. Check input bounds and validation against the PLC's expected domain. A binding can resolve perfectly while a numeric control prevents entry of the installed lane numbers.

Observed source forms include page JSON, XML, and XML `CodeEditorModel` text. Payload extensions do not reliably indicate the embedded format. Some entities are binary and require native tooling. The portable helper extracts text/raw evidence; it does not provide a complete binding validator or HMI renderer.

## Resolve text and alarms

Localization keys can look like readable text IDs. Resolve the resource's `Id`, `DefaultTranslation`, and nested `Text`, and inspect configured languages when relevant. Alarm JSON may include `Expression`, `EventCode`, and a `Message` localization key. Keep these separate:

- The PLC condition that writes a fault.
- The HMI expression that triggers an alarm.
- Its event code and resolved displayed message.

An existing alarm entry can carry an obsolete equipment description. Conversely, a missing regex hit does not prove absent alarm coverage if aliases or aggregated expressions are used. Verify the actual alarm source and mappings.

## Compare screens by function

Use page/control identity, binding, events, input limits, localized text, and access conditions. A removed page may have moved controls onto another screen. Search the full target device before declaring a manual function missing. A resolved-member count establishes only the inspected references' name compatibility, not successful HMI build or runtime behavior.

Treat peer protocols, robots, scanners, AMRs, and cameras similarly: trace the local request/acknowledgement data and state what the external device must guarantee. Do not diagnose network configuration or assert physical transfer semantics from a signal name alone.
