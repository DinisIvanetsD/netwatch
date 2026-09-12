---
name: NetWatch
description: Know what's on your network.
colors:
  signal-blue: "oklch(0.7 0.14 246)"
  night-field: "oklch(0.14 0.012 264)"
  panel-slate: "oklch(0.175 0.012 264)"
  quiet-slate: "oklch(0.22 0.012 264)"
  signal-text: "oklch(0.95 0.004 264)"
  muted-text: "oklch(0.64 0.012 264)"
  hairline-border: "oklch(0.265 0.013 264)"
  active-surface: "oklch(0.24 0.025 250)"
  destructive: "oklch(0.65 0.2 25)"
  status-success: "#34d399"
  status-warning: "#fcd34d"
  status-info: "#7dd3fc"
typography:
  headline:
    fontFamily: "Geist, Geist Fallback, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Geist, Geist Fallback, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist, Geist Fallback, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist, Geist Fallback, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.12em"
  technical:
    fontFamily: "Geist Mono, Geist Mono Fallback, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  sm: "6px"
  md: "9px"
  lg: "10px"
  xl: "15px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
  3xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.signal-blue}"
    textColor: "{colors.night-field}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    height: "36px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted-text}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "36px"
  card:
    backgroundColor: "{colors.panel-slate}"
    textColor: "{colors.signal-text}"
    rounded: "{rounded.lg}"
    padding: "20px"
  input:
    backgroundColor: "{colors.night-field}"
    textColor: "{colors.signal-text}"
    rounded: "{rounded.md}"
    padding: "4px 12px"
    height: "36px"
  status-chip:
    backgroundColor: "{colors.active-surface}"
    textColor: "{colors.signal-text}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
---

# Design System: NetWatch

## Overview

**Creative North Star: "The Operational Radar"**

NetWatch presents network state as a focused control surface for quick detection and response. The radar metaphor is about signal quality, not science-fiction decoration: the interface should tell the administrator what changed, where it happened, and what action is actually possible.

The incumbent system uses a dark neutral field with a cool blue signal accent, restrained tonal layering, and compact operational modules. Typography stays quiet and technical: Geist supports reading and decisions, while Geist Mono identifies IP addresses, MAC addresses, ports, timestamps, and other evidence. The voice is direct and incident-oriented, preferring evidence and next action over spectacle.

The visual system deliberately avoids hacker theatre, Matrix-style backgrounds, neon green dominance, decorative gradients, excessive glow, fake terminal text, and animation that competes with network state.

**Key Characteristics:**

- Radar-like prioritization of live network signals.
- Cool blue action accent used with intention.
- Flat resting surfaces with restrained tonal layers.
- Direct copy that leads with evidence and consequence.
- Technical identifiers set in a selective monospace voice.

## Colors

The palette is a cool, low-noise dark system: a near-black field supports slate panels, a blue accent marks action and live signal, and semantic colors are reserved for status and severity.

### Primary

- **Signal Blue**: The primary action and focus color. Use it for scan actions, active navigation, readiness emphasis, links, and live network signal—not for every decorative highlight.

### Neutral

- **Night Field**: The deepest application canvas and input surface.
- **Panel Slate**: Resting cards, navigation rail, popovers, and grouped operational content.
- **Quiet Slate**: Muted controls, secondary surfaces, and inactive filter groups.
- **Signal Text**: High-contrast headings, device names, and decisions.
- **Muted Text**: Supporting explanations, timestamps, labels, and secondary metadata.
- **Hairline Border**: Structural separation between cards, rows, controls, and navigation regions.
- **Active Surface**: A restrained blue-slate wash for selected navigation and active controls.

### Named Rules

**The Signal Rarity Rule.** Reserve the primary blue accent for actions, active state, focus, and meaningful network signal; the interface should remain calm when nothing needs attention.

## Typography

**Display Font:** Geist (with Geist Fallback and system sans-serif fallbacks)
**Body Font:** Geist (with Geist Fallback and system sans-serif fallbacks)
**Label/Mono Font:** Geist Mono (with Geist Mono Fallback and ui-monospace fallbacks)

**Character:** The pairing is compact, neutral, and operational. Geist keeps dense dashboards readable; Geist Mono turns technical identifiers into clearly scannable evidence without making the product feel like a terminal.

### Hierarchy

- **Headline** (600, 1.5rem, 1.35): Page titles and major error or empty-state headings.
- **Title** (600, 1rem, 1.5): Card titles, device names, and section headings.
- **Body** (400, 0.875rem, 1.5): Descriptions, table content, and operational copy.
- **Label** (600, 0.625rem, 1.4, tracked uppercase): Metric labels, navigation group labels, and compact metadata headings.
- **Technical** (400, 0.75rem, 1.5): IP addresses, MAC addresses, ports, timestamps, and machine-oriented values.

### Named Rules

**The Evidence Before Drama Rule.** Let type hierarchy expose what changed and what can be done; do not enlarge or decorate a value merely to make the screen feel more active.

## Layout

The desktop shell uses a fixed left navigation rail approximately 240px wide, a 64px sticky header, and a centered content region capped at approximately 1600px. Main content uses responsive padding that grows from compact mobile gutters to generous desktop breathing room. Cards and sections follow a compact 8px-based rhythm with consistent 12px, 16px, 20px, 24px, and 32px group spacing.

Operational content is arranged as grids on larger screens and collapses to a single readable column on narrow screens. Device tables remain horizontally scrollable when their evidence columns cannot be safely compressed. On small screens the navigation rail becomes a modal drawer, while the header keeps scan, alert, and settings actions available.

## Elevation & Depth

NetWatch is flat by default and uses tonal layering as its primary depth cue. The background, panel, muted surface, and active surface create hierarchy without making every card float. Borders carry structural meaning. Shadows are reserved for overlays such as tooltips, dialogs, and the mobile navigation drawer, where separation from the page is necessary.

### Shadow Vocabulary

- **Overlay separation** (`0 20px 60px rgba(0, 0, 0, 0.28)`): Use for dialogs and high-priority floating surfaces that must sit above the dashboard.
- **Tooltip separation** (`0 10px 24px rgba(0, 0, 0, 0.24)`): Use for explanatory hover/focus content only.

### Named Rules

**The Flat-By-Default Rule.** Resting cards and panels use border and tonal contrast; elevation appears only when a surface is actually layered above another surface.

## Shapes

The form language uses gently curved corners rather than pills everywhere. Inputs and compact controls use small-to-medium radii, cards use the base medium radius, and status chips alone use a fully rounded silhouette. Borders are one-pixel hairlines with low contrast; they should define structure without becoming a pattern.

Focus is a visible two-pixel ring with offset. Status is communicated by a small dot paired with text, never by color alone. Clipping is limited to cards, drawers, and menus where it protects the content edge.

## Components

Each component is quiet at rest and becomes clearer—not louder—when it enters an active, focus, hover, or warning state.

### Buttons

- **Shape:** Gently curved compact controls (9px radius) with a consistent 36px default height.
- **Primary:** Signal Blue fill with dark text, 8px vertical and 16px horizontal padding; used for scans, saves, and decisive actions.
- **Hover / Focus:** Primary fill steps down slightly on hover; all buttons use a visible two-pixel focus ring; disabled controls reduce opacity and pointer interaction.
- **Secondary / Ghost / Tertiary:** Ghost controls use transparent backgrounds and muted text, gaining a restrained active-surface wash on hover.

### Chips

- **Style:** Fully rounded, compact labels with a low-contrast border and restrained tonal fill.
- **State:** Selected and live states use the blue accent; success, warning, info, and destructive states keep their own semantic colors and remain readable without relying on hue alone.

### Cards / Containers

- **Corner Style:** Base 10px radius, with 20px internal padding for standard cards.
- **Background:** Panel Slate over the Night Field; Quiet Slate and Active Surface are used for subordinate or selected regions.
- **Shadow Strategy:** No shadow at rest; overlays may use the reserved shadow vocabulary.
- **Border:** One-pixel Hairline Border, strengthened only for focus, warning, or readiness state.
- **Internal Padding:** 16px for compact rows and 20px for card regions, with 24px or 32px between major page sections.

### Inputs / Fields

- **Style:** Night Field background, one-pixel border, 9px radius, 36px default height, and 12px horizontal padding.
- **Focus:** A visible ring and clear border contrast, without glow or layout shift.
- **Error / Disabled:** Error uses the destructive semantic color with explanatory text; disabled fields reduce opacity and preserve their labels and values.

### Navigation

- **Style:** A 240px desktop rail with compact 36px rows, muted text by default, and a blue-slate active surface. Section labels use tracked uppercase text.
- **States:** Active navigation includes a small trailing cue; hover changes surface and text contrast without moving the row.
- **Mobile treatment:** The rail becomes a modal drawer with a scrim, close action, preserved focus, and the same navigation order.

### Operational Signal Panels

Summary cards, readiness cards, timelines, and device status rows group a clear label, a primary value, and supporting evidence. Their signature is the pairing of a restrained icon container, concise copy, and a status treatment that explains what the signal means.

## Do's and Don'ts

### Do:

- **Do** reserve the primary blue accent for meaningful actions, active navigation, focus, and live network signal.
- **Do** use Geist Mono selectively for IP addresses, MAC addresses, ports, timestamps, and other technical identifiers.
- **Do** pair every status color with text or a shape cue so state remains understandable without color perception.
- **Do** keep resting surfaces flat and let borders and tonal layers establish structure.
- **Do** lead incident copy with the observed evidence, affected device, time, and available next action.
- **Do** preserve generous content grouping while keeping individual rows compact enough to scan.

### Don't:

- **Don't** use Matrix backgrounds, fake terminal text, neon green dominance, decorative gradients, or gratuitous glow.
- **Don't** make every card or navigation item blue; signal loses meaning when everything is highlighted.
- **Don't** use shadows on ordinary resting cards when a border and tonal layer already provide separation.
- **Don't** communicate severity or device state through color alone.
- **Don't** invent activity, device identity, topology, or certainty in order to make an empty state look busy.
- **Don't** expose raw backend errors or turn technical limitations into unexplained dead ends.
