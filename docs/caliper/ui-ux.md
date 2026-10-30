# UI/UX Principles

## Purpose
Deliver an interface that is clear, responsive and safe for enterprise operators.

## Scope
All web screens, forms, navigation, status displays and error messages.

## Mandatory Rules
- Every destructive action is confirmed and reversible where possible.
- Loading, empty, error and success states are designed for every screen.
- Status is never conveyed by colour alone.
- Forms validate input and preserve user input on failure.
- The interface is usable with keyboard and at mobile widths.

## Recommended Practices
- Show provenance (provider, model, timestamp) for AI-generated content.
- Stream live task progress and make logs accessible.
- Avoid unnecessary modals and dead-end pages.

## Forbidden Practices
- Non-functional buttons or placeholder actions presented as working.
- Hiding failures behind generic success toasts.
- Displaying secrets in the UI.

## Validation Criteria
- All required pages render with real data and explicit empty/error states.
- Accessibility checks for labels, focus and contrast pass.

## Exceptions
Internal debug screens may be less polished but must still be functional.

## Approval Requirements
Branding or navigation changes affecting all users require product approval.

## Version History
- v1 — initial constitutional version.
