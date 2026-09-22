---
version: alpha
name: Aether
description: A frosted-glass design system inspired by Apple's light material language — translucent pill surfaces floating over a soft pearl backdrop, anchored by a charcoal accent.
theme: light
colors:
  primary: "#1d1d1f"
  on-primary: "#f5f5f7"
  secondary: "#54545a"
  tertiary: "#86868b"
  accent: "#0a84ff"
  accent-soft: "rgba(10, 132, 255, 0.16)"
  surface: "#eef1f6"
  surface-glass: "rgba(255, 255, 255, 0.55)"
  surface-glass-strong: "rgba(255, 255, 255, 0.75)"
  surface-raised: "rgba(255, 255, 255, 0.85)"
  on-surface: "#1d1d1f"
  on-surface-muted: "#54545a"
  border: "rgba(15, 23, 42, 0.08)"
  border-strong: "rgba(15, 23, 42, 0.14)"
  bevel-light: "rgba(255, 255, 255, 0.9)"
  bevel-soft: "rgba(255, 255, 255, 0.55)"
  focus: "#0a84ff"
  success: "#34c759"
  warning: "#ff9f0a"
  error: "#ff453a"
  aurora-a: "#c9d6ff"
  aurora-b: "#e3d3ff"
typography:
  font-family-sans: "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
  font-family-mono: "JetBrains Mono, SF Mono, Menlo, monospace"
  display:
    fontSize: 3rem
    lineHeight: 1.16
    letterSpacing: "-0.022em"
    fontWeight: 600
  headline-lg:
    fontSize: 2rem
    lineHeight: 1.25
    letterSpacing: "-0.012em"
    fontWeight: 600
  headline-md:
    fontSize: 1.5rem
    lineHeight: 1.33
    letterSpacing: "-0.012em"
    fontWeight: 600
  body-md:
    fontSize: 0.9375rem
    lineHeight: 1.6
    letterSpacing: "-0.002em"
    fontWeight: 400
  label-sm:
    fontSize: 0.8125rem
    lineHeight: 1.54
    letterSpacing: "0.02em"
    fontWeight: 500
  micro:
    fontSize: 0.6875rem
    lineHeight: 1.45
    letterSpacing: "0.06em"
    fontWeight: 600
    textTransform: uppercase
rounded:
  none: 0
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  full: 9999px
spacing:
  3xs: 2px
  2xs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 72px
elevation:
  glass-bevel: "inset 1.5px 1.5px 0 0 rgba(255,255,255,0.9), inset -1px -1px 0 0 rgba(255,255,255,0.55), inset 0 0 0 1px rgba(15,23,42,0.04)"
  shadow-resting: "0 1px 2px rgba(15,23,42,0.04), 0 12px 28px -10px rgba(15,23,42,0.16)"
  shadow-raised: "0 2px 4px rgba(15,23,42,0.06), 0 22px 44px -14px rgba(15,23,42,0.22)"
  shadow-floating: "0 4px 8px rgba(15,23,42,0.08), 0 32px 64px -16px rgba(15,23,42,0.28)"
  blur-glass: "blur(20px) saturate(180%)"
focus:
  ring: "0 0 0 3px rgba(10, 132, 255, 0.32)"
components:
  button-primary:
    backgroundColor: "{colors.surface-glass-strong}"
    textColor: "{colors.on-surface}"
    typography: "{typography.body-md}"
    rounded: "{rounded.full}"
    height: 52px
    padding: "0 0.375rem 0 1.5rem"
  button-primary-chip:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    size: 40px
  button-secondary:
    backgroundColor: "{colors.surface-glass}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.full}"
    height: 44px
    padding: "0 1.25rem"
  button-tertiary:
    backgroundColor: "transparent"
    textColor: "{colors.secondary}"
    rounded: "{rounded.full}"
    height: 44px
    padding: "0 1.25rem"
  button-solid:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    height: 44px
    padding: "0 1.25rem"
  input-field:
    backgroundColor: "{colors.surface-glass-strong}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.full}"
    height: 48px
    padding: "0 1.125rem"
  card:
    backgroundColor: "{colors.surface-glass-strong}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.xl}"
    padding: "1.5rem"
  card-raised:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.xl}"
    padding: "1.5rem"
  checkbox-default:
    backgroundColor: "{colors.surface-glass-strong}"
    rounded: 7px
    size: 22px
  checkbox-checked:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: 7px
    size: 22px
  switch-track:
    backgroundColor: "rgba(15, 23, 42, 0.1)"
    rounded: "{rounded.full}"
    height: 28px
    width: 48px
  switch-track-on:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.full}"
    height: 28px
    width: 48px
  tabs-container:
    backgroundColor: "{colors.surface-glass}"
    rounded: "{rounded.full}"
    padding: "4px"
  tabs-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    height: 36px
    padding: "0 1rem"
  tabs-inactive:
    backgroundColor: "transparent"
    textColor: "{colors.tertiary}"
    rounded: "{rounded.full}"
    height: 36px
    padding: "0 1rem"
  dock:
    backgroundColor: "{colors.surface-glass-strong}"
    rounded: "{rounded.full}"
    padding: "8px"
  dock-chip:
    backgroundColor: "{colors.surface-glass}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.full}"
    size: 44px
  dock-chip-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    size: 44px
  badge:
    backgroundColor: "{colors.surface-glass}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.full}"
    height: 24px
    padding: "0 0.625rem"
---

## Overview

Aether is a frosted-glass design system that draws on the calm, optical material language of Apple's light interfaces. Every interactive surface reads as a thin translucent pane: a faint inset highlight along the top-left, a softer highlight returning on the bottom-right, a hairline border at low alpha, and a quiet ambient shadow that lifts the pane off a cool pearl backdrop. Pill geometry is the dominant shape — buttons, inputs, tabs, chips, badges, and the signature command dock all share the same continuous radius — and a single charcoal anchor (`#1d1d1f`) carries the weight of primary actions, dark icon chips, and active selections.

The system pairs that material language with an Apple-style typographic voice: tight tracking on display sizes, a 500-weight emphasis tier, and a quiet hierarchy that defers to the glass material. The result is a small token vocabulary that scales from a compact icon button to a hero card without losing its optical identity.

## Colors

The palette is intentionally narrow. A cool pearl (`#eef1f6`) carries the page; three white-alpha surfaces (`0.55`, `0.75`, `0.85`) cover glass panes, raised glass, and the brightest cards. Ink runs through three steps — graphite, slate, mist — so that hierarchy reads without bumping contrast. The accent is a single Apple-style system blue (`#0a84ff`) reserved for focus rings, links, and the on-state of switches; nothing else carries chroma except a faint aurora wash behind hero panes.

| Token | Value | Role |
| --- | --- | --- |
| `colors.surface` | `#eef1f6` | Page background — soft, cool pearl |
| `colors.surface-glass` | `rgba(255,255,255,0.55)` | Standard glass panes and tabs |
| `colors.surface-glass-strong` | `rgba(255,255,255,0.75)` | Buttons, inputs, dock |
| `colors.surface-raised` | `rgba(255,255,255,0.85)` | Hero cards, foreground panels |
| `colors.primary` | `#1d1d1f` | Charcoal anchor for ink and primary action |
| `colors.secondary` | `#54545a` | Secondary text and labels |
| `colors.tertiary` | `#86868b` | Tertiary text, placeholders, inactive |
| `colors.accent` | `#0a84ff` | Focus, links, switch on-state |
| `colors.border` | `rgba(15,23,42,0.08)` | Hairline borders on every glass surface |
| `colors.bevel-light` | `rgba(255,255,255,0.9)` | Top-left inset highlight |

The aurora pair (`#c9d6ff`, `#e3d3ff`) appears only as a soft radial wash on the page background. It exists to give the glass something to refract — never as a fill.

## Typography

Inter handles every text layer. Display sizes use `-0.022em` tracking and weight 600 to mimic SF Pro's optical tightness; body text loosens to `-0.002em` and weight 400 so it reads quietly through the glass. JetBrains Mono is reserved for keyboard hints, numeric chips, and metadata labels — anywhere monospaced tabular figures help the eye scan.

| Token | Size / Line | Weight | Tracking |
| --- | --- | --- | --- |
| `typography.display` | 48 / 56 | 600 | -0.022em |
| `typography.headline-lg` | 32 / 40 | 600 | -0.012em |
| `typography.headline-md` | 24 / 32 | 600 | -0.012em |
| `typography.body-md` | 15 / 24 | 400 | -0.002em |
| `typography.label-sm` | 13 / 20 | 500 | 0.02em |
| `typography.micro` | 11 / 16 | 600 | 0.06em (uppercase) |

Headings should never exceed weight 600; bolder weights break the system's calm voice. Use the `.text-mono` utility for keyboard hints and numeric data.

## Layout

Layouts breathe. A 1200px content frame with `clamp`-style fluid gutters keeps glass panes from crowding each other; the spacing scale climbs through generous steps (`16, 24, 32, 48, 72`) because frosted material needs negative space to read as material. Cards group with `1.5rem` interior padding; sections separate with `3rem` to `4.5rem` of vertical breathing room.

Glass panes prefer single-column stacks at narrow widths and 12-column flex/grid arrangements at desktop. Avoid nesting glass inside glass more than two layers deep — the backdrop filter loses its illusion past the second pass.

## Elevation & Depth

Every interactive surface composes two shadow systems: an **inset bevel** that fakes a glass rim, and an **outset float** that lifts the pane off the pearl background. The bevel never changes between variants; only the float scales up as components rise.

| Token | Composition |
| --- | --- |
| `elevation.glass-bevel` | Top-left light highlight + bottom-right soft highlight + 1px edge contain |
| `elevation.shadow-resting` | Hairline lift + 12px ambient drop |
| `elevation.shadow-raised` | Stronger hairline + 22px ambient drop |
| `elevation.shadow-floating` | Sharp hairline + 32px ambient drop (dock, modals) |
| `elevation.blur-glass` | `blur(20px) saturate(180%)` backdrop filter |

Pressed states tighten the bevel inward (`inset 1px 1px rgba(15,23,42,0.08)`) and remove the highlight — the pane reads as if the user has pushed past the rim.

## Shapes

Pill geometry (`rounded.full`) is the system's defining gesture. Apply it to buttons, inputs, tabs, chips, badges, and the command dock. Cards and panels relax to `rounded.xl` (24px) because the pane needs to hold rectangular content cleanly. Smaller surface embellishments — keyboard chips, the checkbox box, dense inputs — drop to `rounded.md` (12px) or a tuned 7px for the checkbox so the check glyph centers cleanly.

Icon chips are always perfect circles at 40px (inside primary buttons) or 44px (inside the dock). Never square icon containers — the circle is part of the material identity.

## Components

### Buttons

The primary button is the system's anchor: a glass pill that embeds a charcoal `40px` circular icon chip on its right edge. The chip carries the source motif — a dark, lightly inset disc with a light glyph — and animates with a gentle spring on hover. Secondary buttons drop the chip and stay full glass; tertiary buttons remove the pane entirely and surface a wash only on hover. A `btn-solid` variant flips to charcoal fill for high-priority destructive or commit actions.

### Inputs

Inputs share the button's pill, bevel, and shadow tokens. A leading Lucide icon sits at `18px` in tertiary ink; placeholder text matches. Focus replaces the hairline border with a `45%` system-blue stroke and adds the standard focus ring. The `input-area` variant relaxes to a 24px radius so multi-line content has somewhere to breathe.

### Cards

Cards are 24px-radius glass panes with three slots: header, body, footer. A `.card-icon` slot accepts the same charcoal chip used in primary buttons, or a soft glass variant for less-prominent affordances. Use `.card-raised` for hero panes — it lifts the pane onto the `shadow-raised` step and brightens the fill.

### Checkbox & Switch

The checkbox is a 22px glass square with a 7px radius. Checked, it flips to charcoal and reveals a white check glyph built from CSS rotations (no inline SVG required). The switch is a 48×28 pill track with a floating 22px thumb; on-state switches the track to system blue while the thumb stays white with a soft shadow stack.

### Tabs

Tabs live inside a glass pill container at 4px padding. Each tab is a 36px pill; the active tab fills with charcoal and gets a soft 6px drop shadow, so the pane reads as a chip that has snapped into place. Inactive tabs use tertiary ink and brighten to primary on hover.

### Signature — Frosted Command Dock

The dock is the system's hero widget and the place where the full vocabulary compounds. It combines a leading search pill, a row of glass icon chips with an active charcoal state, a vertical hairline divider, and a trailing primary button with the charcoal icon chip. A diagonal refraction overlay sits on the dock itself to add the subtle light bend that makes the material believable. Use it to orient the user, surface global actions, or anchor a landing hero.

### Icon Library

Aether ships with **Lucide** (https://lucide.dev/, ISC). All icons render at `1.75` stroke and inherit `currentColor` from the containing element. Inline browser usage:

```html
<script src="https://unpkg.com/lucide@latest"></script>
<i data-lucide="search"></i>
<script>lucide.createIcons();</script>
```

Never invent SVG paths; if an icon is missing, choose the nearest semantic Lucide glyph.

## Do's and Don'ts

**Do**

- Compose every interactive surface from the same three layers: glass fill, hairline border, inset bevel + outset float.
- Use pill geometry for anything interactive and 24px radius for content containers.
- Reserve charcoal `#1d1d1f` for primary actions, active states, and ink — never as a background fill at scale.
- Let the aurora wash work behind hero glass; keep the page itself calm.
- Use Inter at 500/600 for emphasis and 400 for body. Tighten tracking on display sizes only.

**Don't**

- Don't add chroma to fills outside the system blue accent — saturated buttons break the material.
- Don't nest glass panes more than two deep; the backdrop filter loses its illusion.
- Don't replace pill geometry with hard right angles on interactive elements.
- Don't introduce additional icon libraries or invent custom SVG paths.
- Don't reach for heavier shadows when a component needs emphasis — promote it to `shadow-raised` or `shadow-floating` instead.

## Accessibility

- Body copy (`#54545a` on pearl) clears WCAG AA at body sizes; primary ink (`#1d1d1f`) clears AAA.
- Every interactive surface exposes `:focus-visible` with a 3px `rgba(10,132,255,0.32)` ring on top of the existing bevel; never remove the focus state when restyling.
- Glass surfaces must keep their hairline border — it is the only edge that survives when backdrop filters are unsupported.
- Honor `prefers-reduced-motion`; the system collapses all transitions to `1ms` automatically.

## Framework Adaptation

The system is plain CSS and semantic HTML. To port it:

- Map the YAML token groups above to your framework's token store (CSS variables, Tailwind theme, Style Dictionary, etc.); names are already 1:1 with the CSS custom properties in `system.css`.
- Wrap the component classes (`btn`, `btn-primary`, `input`, `card`, `tabs`, `tab`, `dock`, `dock-chip`) as components in your framework of choice — no class needs JavaScript to function.
- Keep the bevel composition intact. If you must split tokens into separate utilities, never separate the inset highlight from the inset shadow — they exist as a pair.
