# Rubric

Each item is a check you can run against a screenshot or the computed styles, and a
failure you can name. Skip anything the product's own `DESIGN.md` overrides — a declared
system always wins over this file.

## Spacing

- **Every gap comes off one scale** (typically 4/8px or a token set). A 13px gap next to a
  12px one is a defect even though nobody can name it — the eye reads it as sloppiness.
- **Space belongs to the thing above it.** Heading-to-body should be tighter than
  body-to-next-heading. When they're equal, the page loses its grouping and reads as one
  undifferentiated column.
- **Padding is symmetric unless there's a reason.** Optical centering is the exception:
  text with descenders and icon+label pairs often need 1–2px asymmetry to *look* centered.
- **Container padding is consistent across sections.** Mixed 16/20/24 gutters on the same
  page is the single most common "looks off but I can't say why".
- **Nothing touches a viewport edge on mobile** except deliberate full-bleed media.

## Type

- **At most two families**, and one of them should be doing real work — not decoration.
- **Sizes come off a scale** (e.g. 12/14/16/20/24/32/48). Arbitrary 17px and 23px values
  are the tell of hand-tuning without a system.
- **Line length 45–85 characters.** Full-width body text on a desktop monitor is the most
  common readability failure in web apps.
- **Line height scales inversely with size**: ~1.5–1.6 for body, ~1.1–1.25 for display.
  Body leading on a 48px headline looks broken.
- **Letter-spacing**: slightly negative on display sizes, zero on body, slightly positive
  on all-caps labels. Never positive on body text.
- **One weight jump conveys hierarchy** — 400→600. 400→500 is invisible, 400→800 is shouting.

## Hierarchy and layout

- **One primary action per view.** Two equally-weighted primary buttons means neither is.
- **The eye should land where the task starts.** If the loudest element on screen isn't the
  thing the user came to do, the hierarchy is inverted.
- **Alignment**: every element shares an edge with something. Off-by-3px misalignment reads
  as an accident even when nobody spots the cause.
- **Related things are closer than unrelated things.** A label 12px from its own field and
  10px from the next field is a proximity bug.
- **Repeated components look identical.** Two cards with different corner radii or shadow
  depths in one list — pick one.

## Color and contrast

- **Body text ≥ 4.5:1, large text (≥24px or ≥19px bold) ≥ 3:1, UI borders and icons ≥ 3:1.**
  Compute it, don't judge by eye.
- **Color is never the only signal.** Error states need an icon or text, not just red.
- **A palette is 1 accent + neutrals**, plus semantic colors for success/warn/error. Three
  competing accents means no accent.
- **Dark mode is not inverted light mode**: pure #000 backgrounds with #fff text vibrate;
  shadows stop working and must become borders or elevation-by-lightness.
- **Disabled still needs 3:1** against its background, or it reads as a rendering bug.

## States and interaction

- **Every interactive element has hover, focus-visible, active and disabled.** A missing
  `:focus-visible` ring is a blocker, not a polish item — keyboard users are locked out.
- **Tap targets ≥ 44×44px** including padding, even when the icon is 16px.
- **Empty, loading and error states exist and are designed.** A blank white box is not an
  empty state; spinner-only loading with no layout reservation causes layout shift.
- **Content doesn't reflow when data arrives.** Reserve the space (skeleton, min-height).
- **Long strings, zero items, and 999+ items** all render without breaking the layout.

## Motion

- **150–250ms for local feedback, 250–400ms for entering elements.** Under 100ms reads as
  a glitch; over 500ms reads as lag.
- **Ease-out for things entering, ease-in for things leaving.** Linear is only for
  continuous motion like spinners.
- **Animate transform and opacity only.** Animating width, height, top or left forces
  layout on every frame and janks on mid-range hardware.
- **`prefers-reduced-motion` is respected** — required, not optional.
- **Nothing animates on page load** except a single deliberate entrance. Staggered
  fade-in-on-scroll on every section is the most dated pattern on the web.

## AI-slop patterns

Screens generated without a designer converge on the same tells. Each one is a finding:

- Purple-to-blue gradient on the hero, the button, and the icon background.
- Emoji as iconography, or as bullets in a feature list.
- Every card carrying a shadow, a border, *and* a gradient.
- Three feature cards, always three, always icon-title-two-lines-of-lorem.
- Glassmorphism blur applied to something that isn't over an image.
- Centered text down the entire page — no left-aligned reading rhythm anywhere.
- `border-radius` everywhere at the same 12px, including on things that should be square.
- Headline copy in the shape "Beautiful X. Effortless Y." with no concrete claim.
- A dark hero with tiny bright accents and no mid-tones — high contrast standing in for
  hierarchy.
- Fake dashboard screenshots with obviously synthetic data (Acme Inc., $12,345, +12.3%).

The fix is almost always *subtract*: one accent, one elevation level, one radius, and let
spacing and type do the hierarchy.
