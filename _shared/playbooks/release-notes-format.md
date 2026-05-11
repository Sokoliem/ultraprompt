# Release Notes Format

Release notes are user-facing, not developer-facing. Lead with what changed for users; technical detail is secondary.

## Shape (Keep a Changelog style)

```
## [VERSION] - YYYY-MM-DD

### Breaking
- <change> — migration: <link or instructions>

### Added
- <new feature>

### Changed
- <behavior change that's not breaking>

### Deprecated
- <still works but planned for removal in vX>

### Removed
- <no longer present>

### Fixed
- <bug fix>

### Security
- <security fix; CVE if assigned>
```

## Quality bar per entry

- Past tense, action verb: "Added support for X" not "Adds X" or "X is now supported"
- User outcome, not implementation: "Pages now load 30% faster on slow networks" not "Replaced React with Preact"
- One line per entry; details in linked issue/PR if needed
- Group related changes; don't list each commit

## Semver rules

- **Patch**: only Fixed, Security, internal Changed
- **Minor**: Added, Deprecated, non-breaking Changed
- **Major**: any Breaking or Removed entries

If you have a Breaking entry, the version must be a major bump. No exceptions, no "soft breaking" carve-outs.

## Audience

Write for the user who skimmed the previous release notes 3 minutes after waking up. Lead with the thing that affects them most. Bury implementation details.

## What to omit

- Internal refactors (unless they change behavior)
- Dependency bumps (unless they change behavior or fix a CVE)
- Test additions (they're a means, not an end)
- Documentation-only changes (separate notes if needed)
- "Misc" or "Various improvements" — be specific or skip

## Migration sections

For breaking changes, link to a migration guide or include inline:

```
### Breaking
- The `getOrder` API now returns `Order | null` instead of throwing on not-found.

  **Migration**: replace `try/catch` with null check:
  ```js
  // Before
  try { return await getOrder(id); } catch (NotFound) { return null; }
  // After
  return await getOrder(id);  // returns null when not found
  ```
```

## Anti-patterns

- Listing every commit
- Hiding breaking changes in "Other"
- Notes written for developers when the audience is users
- Notes that only document new behavior, not the behavior that changed
- Skipping notes for releases ("nothing user-visible") when the user-visible thing was the dependency rebuild that fixed an unstated bug
