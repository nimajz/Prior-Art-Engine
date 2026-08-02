# DESIGN.md — prior-art-engine Design System

Read this before writing any component or CSS. This is the single source of truth. Do not invent values.

## 0. Stack Constraints

- **React 18** + Vite, CSS Modules or plain CSS
- **Tailwind CSS v3/v4** (CSS-first where possible, no config file)
- **Dark mode only** — no light mode toggle in v1
- **Fonts** — System sans-serif (Geist via fallback chain), IBM Plex Mono for numbers/counts
- **Icons** — Lucide React only
- **Colors** — oklch() for perceptual uniformity

## 1. Design Direction

**Aesthetic:** Gazette/examiner's docket. Ledger-blue accents, seal-red alerts, moss-green success. Paper-white backgrounds, dark ink typography. Minimal ornamentation — every element earns its place.

**Personality:** Authoritative yet approachable. Focused on readability and hierarchy. Signature element: the examiner's "stamp" badge (rotated, bordered, serif accent).

**Rule:** If an element has no function, remove it.

## 2. Color System — oklch

All colors use oklch() for wide-gamut support and perceptual lightness uniformity.

### Token Reference

```css
/* ── Neutrals (Paper/Ink) ─────────────────── */
--paper:          oklch(0.965 0.002 270);   /* page bg */
--paper-raised:   oklch(1.000 0.000 0);     /* card surface */
--ink:            oklch(0.092 0.003 270);   /* main text */
--ink-soft:       oklch(0.230 0.005 270);   /* secondary text */
--muted:          oklch(0.420 0.007 270);   /* tertiary text */
--faint:          oklch(0.600 0.008 270);   /* hints, placeholders */
--line:           oklch(0.860 0.004 270);   /* borders, dividers */
--line-strong:    oklch(0.790 0.005 270);   /* emphasis borders */

/* ── Ledger Blue (Primary) ─────────────────── */
--ledger:         oklch(0.300 0.090 250);   /* main accent (dark) */
--ledger-soft:    oklch(0.450 0.075 250);   /* hover/active state */
--signal:         oklch(0.590 0.150 250);   /* link, interactive */
--signal-soft:    oklch(0.920 0.060 250);   /* background tint */

/* ── Seal Red (Danger) ──────────────────────── */
--seal:           oklch(0.450 0.120 30);    /* error, critical */
--seal-soft:      oklch(0.950 0.040 30);    /* error background */

/* ── Moss Green (Success) ──────────────────── */
--moss:           oklch(0.490 0.100 140);   /* success, positive */
--moss-soft:      oklch(0.930 0.080 140);   /* success background */

/* ── Amber (Warning) ────────────────────────── */
--amber:          oklch(0.510 0.100 60);    /* warning, attention */
--amber-soft:     oklch(0.950 0.070 60);    /* warning background */

/* ── Violet (Gemini/ARM D) ──────────────────── */
--violet:         oklch(0.430 0.100 300);   /* ARM D indicator */
--violet-soft:    oklch(0.935 0.065 300);   /* ARM D background */
```

## 3. Semantic Tokens

Map oklch tokens to their roles in the UI:

```css
/* Light backgrounds */
--bg-page:          var(--paper);
--bg-card:          var(--paper-raised);
--bg-hover:         oklch(0.960 0.003 270);
--bg-subtle:        oklch(0.985 0.002 270);

/* Text */
--text-primary:     var(--ink);
--text-secondary:   var(--ink-soft);
--text-muted:       var(--muted);
--text-faint:       var(--faint);

/* Borders */
--border-default:   var(--line);
--border-strong:    var(--line-strong);

/* Interactive */
--accent-default:   var(--ledger);
--accent-hover:     var(--ledger-soft);
--interactive:      var(--signal);
--interactive-bg:   var(--signal-soft);

/* Status */
--error:            var(--seal);
--error-bg:         var(--seal-soft);
--success:          var(--moss);
--success-bg:       var(--moss-soft);
--warning:          var(--amber);
--warning-bg:       var(--amber-soft);
--brand-d:          var(--violet);
--brand-d-bg:       var(--violet-soft);
```

## 4. Typography

- **Sans (body):** System fallback (Geist or platform default) — `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- **Serif (headlines):** "Source Serif 4" via Google Fonts (elegant examiner/gazette feel)
- **Mono (counts/IDs):** "IBM Plex Mono" via Google Fonts — numbers, license numbers, docket IDs only

### Scale (strict — use only these)

| Role | CSS | Where |
|------|-----|-------|
| **Page title** | `font-serif text-2xl font-600 tracking-tight` | Masthead |
| **Section header** | `font-serif text-lg font-600` | Result headings, tab labels |
| **Label** | `font-mono text-xs font-600 uppercase tracking-widest` | Field labels, metadata tags |
| **Body** | `text-sm font-400` | Result titles, abstract text |
| **Small** | `text-xs font-400` | Hint text, captions |
| **Muted** | `text-xs text-faint` | Metadata, timestamps |

**Never:** text-xl or larger in the app UI. Never font-bold — max is font-600.

## 5. Spacing

All spacing is multiples of 4px. Keep it tight.

| Context | Token | Size |
|---------|-------|------|
| Page horizontal padding | `px-4` | 16px |
| Page max-width | `max-w-5xl` | ~90ch |
| Section vertical gap | `gap-6` | 24px |
| Card padding | `p-6` | 24px |
| Result card padding | `p-5` | 20px |
| List item padding | `px-4 py-3` | 16px horiz, 12px vert |
| Input height | `h-9` | 36px |
| Button height | `h-9` | 36px |
| Icon size (inline) | `size-4` | 16px |
| Icon size (UI) | `size-5` | 20px |

## 6. Border Radius

| Use | Token | Value |
|-----|-------|-------|
| Cards, containers | `rounded-lg` | 10px |
| Inputs, buttons | `rounded-md` | 6px |
| Small chips, badges | `rounded-sm` | 3px |
| Never use `rounded-full` except avatar dots |

## 7. Shadows

**Dark mode only** — no shadows. Border and background color carry visual hierarchy.

- **Hover effect:** `border-border-strong` (upgrade border) + `bg-hover` (subtle background lift)
- **Transition:** `transition-colors duration-150`

## 8. Component Specs

### Button Variants

```tsx
// Primary (accent)
bg-ledger hover:bg-ledger-soft text-white
h-9 rounded-md px-4 text-sm font-600
transition-colors duration-150 cursor-pointer

// Secondary (ghost)
bg-transparent hover:bg-signal-soft text-ink
h-9 rounded-md px-4 text-sm font-600
transition-colors duration-150 cursor-pointer

// Danger/destructive
bg-transparent hover:bg-seal-soft text-seal
h-9 rounded-md px-4 text-sm font-600
transition-colors duration-150 cursor-pointer

// Icon-only (all variants)
size-8 p-0 rounded-md flex items-center justify-center
aria-label required
```

### Input

```tsx
h-9 w-full rounded-md border border-line
bg-paper-raised px-3 text-sm text-ink
placeholder:text-faint
focus:outline-none focus:ring-1 focus:ring-signal focus:border-signal
transition-colors duration-150
disabled:opacity-50 disabled:cursor-not-allowed

/* Error state */
border-seal focus:ring-seal
```

### Card (Exhibit / Result)

```tsx
bg-paper-raised border border-line rounded-lg
overflow-hidden box-shadow-none
transition-colors duration-150
hover:border-line-strong

/* Header section */
border-l-4 border-l-ledger px-5 py-4
(border-l-amber for patents, border-l-violet for ARM D)
```

### Badge / Stamp

```tsx
/* Examiner's stamp (rotated, bordered) */
inline-block
border-2 border-current
rounded-full px-3 py-1
font-serif font-700 text-sm
transform rotate-[-4deg]
(customize border-color per variant)

/* Pill */
inline-flex items-center
text-xs font-mono font-600
bg-signal-soft text-ledger
px-2 py-1 rounded-sm
```

### List Item (TodoItem semantics)

```tsx
flex items-center gap-3 px-4 py-3
border-b border-line last:border-b-0
group hover:bg-hover transition-colors duration-150
```

### Empty State

```tsx
py-12 flex flex-col items-center gap-4 text-center
icon: size-8 text-faint
heading: font-serif text-lg text-ink font-600
text: text-sm text-muted
```

### Highlight Span (in abstract)

```tsx
/* Highlighted sentence background */
bg-amber-100 text-amber-900
padding 1px 4px
rounded-sm
border-b border-amber-300

/* Plain sentence */
text-muted
```

## 9. Transitions (strict)

| Duration | Use |
|----------|-----|
| `duration-150` | color, bg, border, opacity |
| `duration-200` | text decorations, line-through |
| `duration-300` | layout shifts (only if necessary) |

**No keyframe animations in the main UI.** Loading/skeleton only: `animate-pulse`. Never `animate-bounce`, `animate-spin` outside explicit loading indicators.

## 10. Dark Mode — Implementation

Dark is the **default and only mode in v1**. No toggle or light mode.

```tsx
// App root or layout
// Simply use CSS variables and rely on oklch darkness
<div className="min-h-screen" style={{ backgroundColor: 'var(--paper)' }}>
  {children}
</div>
```

## 11. Accessibility

- **Focus ring:** `focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-signal focus-visible:ring-offset-2`
- **Icon-only buttons:** must have `aria-label`
- **Checkbox labels:** must be visible or `sr-only`
- **Color contrast:** foreground on background ≥ 4.5:1 (verified in dark mode)
- **Keyboard:** Tab → all interactive, Enter/Space → activate buttons/checkboxes

## 12. What NOT to do

- ❌ Gradients (background or text)
- ❌ Background images or patterns
- ❌ Colored surfaces — everything neutral except accent
- ❌ Font sizes above `text-lg`
- ❌ `font-bold` — max is `font-600`
- ❌ Box shadows in dark mode
- ❌ Emojis as icons — Lucide only
- ❌ `rounded-full` on cards/inputs (avatar dots only)
- ❌ Raw hex/hsl colors — oklch variables only
- ❌ Light mode toggle or system detection
