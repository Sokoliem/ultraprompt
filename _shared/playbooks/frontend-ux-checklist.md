# Frontend UX Checklist

UX review for web frontends. For accessibility-specific review, use the `accessibility-review` skill — this checklist is broader.

## Loading states

- [ ] Initial load: skeleton or spinner shown within 100ms of navigation
- [ ] Action feedback: button click → loading state within 100ms
- [ ] Long operations: progress indication after ~1s; ability to cancel where appropriate
- [ ] Empty states: meaningful "no items yet" UI, not a blank screen

## Error states

- [ ] Error messages are actionable ("network connection lost — retry" not "error code 5023")
- [ ] Form errors point to the field and explain what's wrong
- [ ] Server errors don't expose stack traces or internal IDs to end users
- [ ] Failed actions don't leave the UI in an inconsistent state (button stuck loading)

## Form quality

- [ ] Required fields marked clearly (asterisk + accessible label)
- [ ] Validation runs on blur, not just on submit
- [ ] Submit button disabled while submitting (prevent double-submit)
- [ ] After successful submit: navigate or clear the form; don't leave the user wondering
- [ ] Autofocus the first field on entry (where it doesn't conflict with assistive tech)

## Navigation

- [ ] Browser back button works as expected (history is sane)
- [ ] Direct linking to deep states works (no SPA-only routes that 404 on refresh)
- [ ] Breadcrumbs or visible hierarchy for nested screens
- [ ] Active nav item is visually distinct

## Performance

- [ ] First Contentful Paint < 2s on 3G simulation
- [ ] Largest Contentful Paint < 2.5s
- [ ] No layout shift after content loads (images and ads have reserved space)
- [ ] Interactive elements respond to input within 100ms

## Mobile / responsive

- [ ] Tap targets ≥ 44×44 px
- [ ] No horizontal scroll on standard phone sizes (375px wide)
- [ ] Forms work with on-screen keyboards (input types set: email, tel, number)
- [ ] Long content scrollable without breaking layout

## State persistence

- [ ] Refreshing the page doesn't lose unsaved work (warn or auto-save)
- [ ] Filters / sort / pagination persist across navigation back
- [ ] Form state survives accidental tab close where appropriate (drafts)

## Visual hierarchy

- [ ] Primary action visually dominant (one primary button per screen)
- [ ] Destructive actions visually distinct from neutral (red, secondary placement)
- [ ] Type scale is consistent (use design tokens, not arbitrary px values)

## Internationalization

- [ ] Strings extracted; no hardcoded user-visible text in components
- [ ] Layout doesn't break with longer translations (German, Russian)
- [ ] Date/number formatting respects locale
- [ ] RTL languages work (if supported)

## What to skip

This checklist is for review; not every box must be ticked for every component. Use it to find the items that are missing. For accessibility-specific depth, hand off to `accessibility-review`.
