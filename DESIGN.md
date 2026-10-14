---
name: CourseMax LearnHouse native workspace
description: Observed native dashboard patterns, preserved by the synthetic Classes extension.
colors:
  focus: "#171717"
  selection-bg: "#e5e7eb"
  selection-text: "#111827"
rounded:
  control: "8px"
spacing:
  compact: "8px"
  group: "16px"
---

# Design System: CourseMax LearnHouse

## Overview

Preserve LearnHouse's native visual world: dark dashboard rail, off-white workspace, white data surfaces, existing sans typography and restrained rounded controls. This document records observed patterns, not approval for a global redesign or a new brand metaphor.

## Colors

Neutral surfaces carry content; amber and green communicate review and linked evidence, always accompanied by text. The frontmatter captures literal scoped focus/selection colors from `preview.module.css`; shared palette authority remains the native styles and UI components.

## Typography

Retain existing native sans typography. Classes uses a 30px task heading, 14px body/controls and 12px supporting labels. Thai text wraps naturally; identifiers remain readable data, not decorative monospace.

## Layout

Group related rows inside a shared white surface rather than repeat full configuration cards. Desktop roster tables become stacked records below 768px. Search and filters precede results. Keep context and primary action discoverable without horizontal scrolling.

## Elevation & Depth

Use native understated borders and existing soft control shadows. Do not introduce decorative glass, hard offset shadows or simulated materials.

## Shapes

Use existing rounded neutral controls and native dialogs. Scoped controls have a minimum 44px height; compact status labels do not behave like buttons.

## Components

Reuse `components/ui/button`, `input`, `dialog` and `DashTabBar`. Preserve their states and native navigation. Protected confirmation uses a dialog; sustained case review occupies the workspace. Use Lucide icons rather than glyphs. Scoped keyboard focus uses an offset outline; selection and caret colors are explicit. Respect reduced motion.

## Do's and Don'ts

- Do keep membership, account linkage and review status visually distinct.
- Do include natural Thai and English labels, useful empty/error/retry states and visible focus.
- Don't grant actual permissions through demo role selectors.
- Don't promote preview-only composition or inherited shell defects into new global design rules.

Evidence: compiled 1440/390 English/Thai Classes, roster, review and owned-identity task captures, 2026-10-14. Inline finish review, not independent review. No new shipping raster assets. Shared native shell is preserved; broader shell accessibility/branding acceptance is outside this record.
