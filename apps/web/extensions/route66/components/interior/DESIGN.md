# Custom LearnHouse material layer

Owner-pinned Interior, upstream commit `314800833bf01e23e6ae74c2a17fbdaac3688c84`, MIT. See `LICENSE` and `docs/extensions/interior-ui.md`. This is the extension's visual system, not a replacement for the native LearnHouse shell.

## Built materials

- **Bezel** white frame, inherited LearnHouse typography. Designed for the existing light account UI used in classrooms and everyday daylight; no new theme switch or font.
- **Panel** white content lifted by a thin perimeter and soft shadow. Use the `panel` class for original-document evidence and existing content cards, not every data row.
- **Well** recessed controls and filter areas, white or `#fafafa`. Keep visible labels and native date/select behavior.
- **Cap** a 44px minimum control with a small bottom lip. Dark `#131313` is the primary action; secondary actions stay white and cancellation stays quiet. Only selected navigation receives a raised cap; inactive options remain transparent in their recessed rail.

Ink `#131313`, secondary `#454545`, muted `#6e6e6e`; focus `#4568ff` and selection `#edf1ff`. Preserve existing semantic status/weekday palettes and their written labels. Do not turn school confirmation or green status into an implication of enrollment, publication or permission.

## Interaction and accessibility

Shared `Button` wraps the native LearnHouse button/Slot, adding optional reserved-space loading faces. `CopyButton` uses Interior's headless clipboard pattern with visible/live feedback, fallback and focus restoration. `SegmentedControl` owns only controlled radio selection and roving keyboard focus; existing callers retain panel, draft and request state. Native Input, form submission, Radix tabs/dialogs, date/select fields and disclosures remain behavioral authorities. There is no new dependency, request timer or simulated academic success; clipboard feedback alone resets after two seconds. Existing NRRU panels remain mounted so navigation preserves search and unsaved drafts. Pressed controls move 1px; reduced-motion removes travel and transitions. Forced-color mode retains outlines, selection cues and control boundaries. Theme text selection, caret and scrollbars inside the scope only.

The classes landing page has one compact native tab rail for NRRU classes, LearnHouse classes and School calendar. Never stack account links, source selection and a second class/calendar rail. Account settings remain in the native sidebar/mobile navigation. Keep desktop labels on one line; mobile labels may wrap inside their touch targets, not onto additional control rows.

Use shared `Button` via the UI adapter, `CopyButton` for clipboard actions and `SegmentedControl` for exclusive choices. Keep native Radix tabs when selecting mounted panels and native calendar-day buttons where a generic choice rail would lose the grid semantics. Add `scope` to an active custom root, `navigation` only where a routing layer genuinely needs it, and `panel`/`well` only where those materials clarify the task. Never apply it to an ancestor of native account navigation, the whole document, retired preview fixtures or organization administration. Do not override `[hidden]`, native disabled state, fieldset behavior or academic confirmation gates.

No shipping raster assets were added. Isolated fixture screenshots are validation evidence, not institutional or provider acceptance.
