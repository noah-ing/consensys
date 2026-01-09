# Bugs Found During Playwright Testing

**Test Date:** 2026-01-08
**Testing Tool:** Playwright 1.57.0
**Browser:** Chromium (headless)
**Test File:** tests/test_web_ui.py

---

## Summary

During automated Playwright testing of the Consensys web UI, the following bugs were observed intermittently. Note that these bugs may occur depending on the API response timing and content.

| Bug ID | Severity | Component | Status |
|--------|----------|-----------|--------|
| BUG-001 | Medium | Consensus Panel | Intermittent |
| BUG-002 | High | Reviews Container | Intermittent |
| BUG-003 | Medium | Export Panel | Intermittent |
| BUG-004 | Low | Fix Suggestions | By Design |

---

## BUG-001: Consensus Panel Not Visible After Review

**Component:** Consensus Panel (`#consensus-panel`)
**Severity:** Medium
**Status:** Intermittent - depends on API response

### Description
After a code review completes and the results section becomes visible, the consensus panel may not appear. This happens when the review completes in "quick mode" where only Round 1 reviews are performed without the full debate and voting process.

### Steps to Reproduce
1. Navigate to localhost:8080
2. Enter Python code with security issues
3. Enable "Quick mode" checkbox
4. Click "Review Code" button
5. Wait for results to load
6. Observe consensus panel may not appear

### Expected Behavior
Consensus panel should show a summary decision even in quick mode.

### Actual Behavior
Consensus panel stays hidden in quick mode, only visible in full debate mode.

### Screenshot
See: `docs/screenshots/05_no_consensus_panel.png`

---

## BUG-002: Reviews Container Empty

**Component:** Reviews Container (`#reviews-container`)
**Severity:** High
**Status:** Intermittent

### Description
In some test runs, the reviews container appears empty even after the results section becomes visible. This appears to be a timing issue where the reviews are still being processed.

### Workaround
Add a 2-second wait after results section becomes visible before checking for reviews.

### Screenshot
See: `docs/screenshots/04_results_loaded.png`

---

## BUG-003: Export Panel Not Visible

**Component:** Export Panel (`#export-panel`)
**Severity:** Medium
**Status:** Intermittent

### Description
Export panel (Markdown, JSON, GitHub export buttons) may not appear after review completes. This is related to BUG-001 as the export panel visibility is tied to having complete review data.

### Screenshot
See: `docs/screenshots/09_no_export_panel.png`

---

## BUG-004: Fix Suggestions Panel Not Showing Fixes

**Component:** Fix Suggestions Panel (`#fixes-panel`)
**Severity:** Low
**Status:** By Design

### Description
The fix suggestions panel only appears when the AI agents provide specific code fixes in their reviews. If no fixes are suggested, the panel remains hidden. This is expected behavior but could be confusing to users.

### Recommendation
Show the panel with a message like "No fixes suggested" rather than hiding it completely.

### Screenshot
See: `docs/screenshots/06_no_fixes.png`

---

## Test Results Summary

All 12 Playwright tests pass successfully:

- **TestPageLoad** (2 tests): PASSED
- **TestCodeSubmission** (1 test): PASSED
- **TestFixSuggestionsPanel** (1 test): PASSED
- **TestDiffView** (1 test): PASSED
- **TestApplyAllFixes** (1 test): PASSED
- **TestExportFunctionality** (1 test): PASSED
- **TestQuickActionsPanel** (1 test): PASSED
- **TestDarkMode** (1 test): PASSED
- **TestMobileViewport** (1 test): PASSED
- **TestHistoryModal** (1 test): PASSED
- **TestEndToEnd** (1 test): PASSED

---

## Screenshots Captured

Located in `docs/screenshots/`:

| Screenshot | Description |
|------------|-------------|
| 01_page_load.png | Initial page load |
| 02_code_entered.png | Code entered in textarea |
| 03_processing.png | Review in progress |
| 04_results_loaded.png | Results section visible |
| 05_consensus_panel.png / 05_no_consensus_panel.png | Consensus state |
| 06_fixes_panel.png / 06_no_fixes.png | Fix suggestions |
| 07_diff_view_toggled.png | Diff view toggle |
| 08_apply_fixes_panel.png | Apply all fixes |
| 09_export_panel.png | Export options |
| 10_quick_actions_panel.png | Quick actions |
| 11_initial_theme.png | Light theme |
| 11a_after_toggle.png | After theme toggle |
| 11c_dark_mode_with_results.png | Dark mode with results |
| 12_mobile_viewport.png | Mobile view (375px) |
| 13_history_modal.png | History modal |
| e2e_*.png | End-to-end test steps |
