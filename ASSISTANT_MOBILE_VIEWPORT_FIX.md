# Assistant Mobile Viewport Stability Fix

## Scope
UI/UX-only fix for the floating SymptoSense assistant on mobile Safari/iPhone.

## Problem
Opening the assistant or selecting a health-question path programmatically focused the chat input. On iOS Safari, programmatic focus can move the visual viewport. The page behind the assistant also remained scrollable, so the background appeared to jump/move while the assistant was open.

## Changes
- Lock the document at its exact current scroll position while the assistant is open.
- Restore the same scroll position when the assistant closes.
- Prevent background overscroll while keeping `.asst-body` independently scrollable.
- Disable automatic input focus on touch/mobile viewports.
- Keep desktop auto-focus using `focus({preventScroll:true})` where supported.
- Use the same safe-focus helper for health-question and mental-health assistant paths.

## Unchanged
- Assistant API/backend logic
- AI responses
- Authentication/database
- Medical logic
- Routes
- Existing assistant features

## Verification
- `python -m py_compile webapp.py`: passed.
- Static regression checks confirm page-lock CSS/JS exists and mobile assistant open no longer directly calls `input.focus()`.
- Full browser automation was not run because the local runtime does not include Flask/Groq dependencies.
