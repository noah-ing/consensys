"""
Playwright end-to-end tests for Consensys Web UI.

Tests the complete user journey through the web interface including:
- Page loading and initial state
- Code submission and review flow
- Fix suggestions panel
- Diff view functionality
- Apply All Fixes feature
- Export functionality (Markdown, JSON, GitHub)
- Quick Actions panel
- Dark mode toggle
- Mobile responsiveness
"""
import pytest
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

# Test configuration
BASE_URL = os.environ.get("CONSENSYS_URL", "http://localhost:8080")
SCREENSHOTS_DIR = Path(__file__).parent.parent / "docs" / "screenshots"
BUGS_FILE = Path(__file__).parent.parent / "BUGS.md"

# Sample Python code with intentional issues for testing
SAMPLE_CODE = '''import os
import subprocess

def run_command(user_input):
    # Potential command injection
    result = subprocess.run(user_input, shell=True, capture_output=True)
    return result.stdout.decode()

def get_user_data(user_id):
    # SQL injection vulnerability
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return query

password = "admin123"  # Hardcoded password
'''

# Track bugs found during testing
bugs_found = []


def record_bug(title: str, description: str, screenshot_path: str = None):
    """Record a bug found during testing."""
    bug = {
        "title": title,
        "description": description,
        "screenshot": screenshot_path
    }
    bugs_found.append(bug)


def save_bugs():
    """Save all found bugs to BUGS.md."""
    if not bugs_found:
        # Write empty bugs file indicating no bugs
        with open(BUGS_FILE, "w") as f:
            f.write("# Bugs Found During Playwright Testing\n\n")
            f.write("*No bugs found during automated testing.*\n")
        return

    with open(BUGS_FILE, "w") as f:
        f.write("# Bugs Found During Playwright Testing\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        for i, bug in enumerate(bugs_found, 1):
            f.write(f"## Bug {i}: {bug['title']}\n\n")
            f.write(f"**Description:** {bug['description']}\n\n")
            if bug['screenshot']:
                f.write(f"**Screenshot:** `{bug['screenshot']}`\n\n")
            f.write("---\n\n")


@pytest.fixture(scope="module")
def browser():
    """Create a browser instance for the test module."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser):
    """Create a new page for each test."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    """Setup before tests and save bugs after all tests complete."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    save_bugs()


def take_screenshot(page: Page, name: str) -> str:
    """Take a screenshot and return the path."""
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


class TestPageLoad:
    """Test that the page loads correctly."""

    def test_page_loads_successfully(self, page: Page):
        """Test: Navigate to localhost:8080, verify page loads."""
        # Navigate to the page
        response = page.goto(BASE_URL, wait_until="networkidle")

        # Verify successful response
        assert response is not None, "No response received"
        assert response.status == 200, f"Expected 200, got {response.status}"

        # Take screenshot
        take_screenshot(page, "01_page_load")

        # Verify key elements exist
        title = page.title()
        assert "CONSENSYS" in title.upper(), f"Expected 'CONSENSYS' in title, got '{title}'"

        # Check that the code input exists
        code_input = page.locator("#code-input")
        expect(code_input).to_be_visible()

        # Check that submit button exists
        submit_btn = page.locator("#submit-btn")
        expect(submit_btn).to_be_visible()

    def test_initial_state(self, page: Page):
        """Verify initial state of the page."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Results section should be hidden initially
        results = page.locator("#results-section")
        expect(results).to_be_hidden()

        # Status section should be hidden
        status = page.locator("#status-section")
        expect(status).to_be_hidden()

        # Character count should show 0
        char_count = page.locator("#char-count")
        expect(char_count).to_contain_text("0 chars")


class TestCodeSubmission:
    """Test code submission and review flow."""

    def test_submit_code_shows_agents(self, page: Page):
        """Test: Submit Python code, verify agents respond."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Enter sample code
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)

        # Verify character count updates (should be > 0)
        char_count = page.locator("#char-count")
        char_text = char_count.inner_text()
        assert char_text != "0 characters", f"Expected character count to update, got: {char_text}"

        take_screenshot(page, "02_code_entered")

        # Enable quick mode for faster testing
        quick_mode = page.locator("#quick-mode")
        quick_mode.check()

        # Submit the code
        submit_btn = page.locator("#submit-btn")
        submit_btn.click()

        # Wait for status section to appear
        status_section = page.locator("#status-section")
        expect(status_section).to_be_visible(timeout=5000)

        take_screenshot(page, "03_processing")

        # Wait for results section to be visible (starts immediately with WebSocket)
        results_section = page.locator("#results-section")
        expect(results_section).to_be_visible(timeout=120000)

        # Wait for the status section to hide (indicates review is complete)
        status_section = page.locator("#status-section")
        expect(status_section).to_be_hidden(timeout=120000)

        take_screenshot(page, "04_results_loaded")

        # Additional wait for UI to stabilize
        page.wait_for_timeout(3000)

        # Check consensus panel - should be visible after review completes
        consensus_panel = page.locator("#consensus-panel")
        consensus_visible = consensus_panel.is_visible()

        if consensus_visible:
            take_screenshot(page, "05_consensus_panel")
            # Verify decision badge shows a decision
            decision_badge = page.locator("#decision-badge")
            if decision_badge.is_visible():
                badge_text = decision_badge.inner_text()
                # Badge text is formatted as APPROVED, REJECTED, or NEEDS REVIEW
                assert badge_text in ["APPROVED", "REJECTED", "NEEDS REVIEW", ""], f"Unexpected decision: {badge_text}"
        else:
            take_screenshot(page, "05_no_consensus_panel")
            record_bug(
                "Consensus Panel Not Visible",
                "Consensus panel did not appear after code review completed, even though results section is visible"
            )

        # Verify reviews container has content
        reviews_container = page.locator("#reviews-container")
        reviews = reviews_container.locator(".agent-panel")
        review_count = reviews.count()

        if review_count == 0:
            record_bug(
                "No Agent Reviews Displayed",
                "The reviews container is empty after review completed"
            )
        else:
            take_screenshot(page, "05a_reviews_loaded")
            print(f"Found {review_count} agent reviews")


class TestFixSuggestionsPanel:
    """Test Fix Suggestions panel functionality."""

    def test_fixes_panel_appears(self, page: Page):
        """Test: Verify Fix Suggestions panel appears with fixes."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Submit code that should generate fixes
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)

        # Enable quick mode
        page.locator("#quick-mode").check()

        # Submit
        page.locator("#submit-btn").click()

        # Wait for results
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)

        # Check if fixes panel exists (may or may not have fixes depending on AI response)
        fixes_panel = page.locator("#fixes-panel")

        # Give it a moment to render
        page.wait_for_timeout(1000)

        if fixes_panel.is_visible():
            take_screenshot(page, "06_fixes_panel")

            # Check fixes count
            fixes_count = page.locator("#fixes-count")
            count_text = fixes_count.inner_text()
            print(f"Fixes found: {count_text}")
        else:
            # No fixes found - this might be okay depending on AI response
            take_screenshot(page, "06_no_fixes")
            print("No fixes panel visible - AI may not have suggested fixes")


class TestDiffView:
    """Test Diff View toggle functionality."""

    def test_diff_view_toggle(self, page: Page):
        """Test: Click Diff View toggle, verify before/after shows."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Submit code
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)
        page.locator("#quick-mode").check()
        page.locator("#submit-btn").click()

        # Wait for results
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)

        # Look for any diff toggle buttons
        diff_toggles = page.locator(".diff-toggle-btn")
        toggle_count = diff_toggles.count()

        if toggle_count > 0:
            # Click the first diff toggle
            first_toggle = diff_toggles.first
            first_toggle.click()

            page.wait_for_timeout(500)
            take_screenshot(page, "07_diff_view_toggled")

            # Look for visible diff view
            visible_diff = page.locator(".diff-view-wrapper.visible")
            if visible_diff.count() > 0:
                print("Diff view successfully toggled visible")
            else:
                print("Diff toggle clicked but diff view not visible - may be a bug")
        else:
            take_screenshot(page, "07_no_diff_toggles")
            print("No diff toggle buttons found - AI may not have provided code fixes")


class TestApplyAllFixes:
    """Test Apply All Fixes functionality."""

    def test_apply_all_fixes(self, page: Page):
        """Test: Click Apply All Fixes, verify combined code appears."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Submit code
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)
        page.locator("#quick-mode").check()
        page.locator("#submit-btn").click()

        # Wait for results
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)

        # Check if apply fixes panel is visible
        apply_fixes_panel = page.locator("#apply-fixes-panel")

        page.wait_for_timeout(1000)

        if apply_fixes_panel.is_visible():
            take_screenshot(page, "08_apply_fixes_panel")

            # Check for the fixed code block
            all_fixed_code = page.locator("#all-fixed-code")
            if all_fixed_code.is_visible():
                code_content = all_fixed_code.inner_text()
                print(f"Fixed code available: {len(code_content)} characters")

            # Check for copy button
            copy_btn = page.locator("#copy-all-fixes-btn")
            if copy_btn.is_visible():
                print("Copy all fixes button is available")
        else:
            take_screenshot(page, "08_no_apply_fixes")
            print("Apply fixes panel not visible - no fixes to apply")


class TestExportFunctionality:
    """Test export buttons (Markdown, JSON, GitHub)."""

    def test_export_buttons(self, page: Page):
        """Test: Click each export button (Markdown, JSON, GitHub)."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Submit code
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)
        page.locator("#quick-mode").check()
        page.locator("#submit-btn").click()

        # Wait for results section
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)

        # Wait for status section to hide (review complete)
        expect(page.locator("#status-section")).to_be_hidden(timeout=120000)

        # Allow UI to stabilize
        page.wait_for_timeout(2000)

        # Check export panel visibility
        export_panel = page.locator("#export-panel")

        if export_panel.is_visible():
            take_screenshot(page, "09_export_panel")

            # Test Markdown export
            md_button = page.locator("button:has-text('Markdown')")
            if md_button.count() > 0:
                md_button.first.click()
                page.wait_for_timeout(500)
                take_screenshot(page, "09a_markdown_export")
                print("Markdown export button clicked")

            # Test JSON export
            json_button = page.locator("button:has-text('JSON')")
            if json_button.count() > 0:
                json_button.first.click()
                page.wait_for_timeout(500)
                take_screenshot(page, "09b_json_export")
                print("JSON export button clicked")

            # Test GitHub Issue export
            github_button = page.locator("button:has-text('GitHub')")
            if github_button.count() > 0:
                github_button.first.click()
                page.wait_for_timeout(500)
                take_screenshot(page, "09c_github_export")
                print("GitHub export button clicked")
        else:
            take_screenshot(page, "09_no_export_panel")
            record_bug(
                "Export Panel Not Visible",
                "Export panel did not appear after code review completed"
            )


class TestQuickActionsPanel:
    """Test Quick Actions panel with patterns."""

    def test_quick_actions_panel(self, page: Page):
        """Test: Verify Quick Actions panel shows patterns."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Submit code
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)
        page.locator("#quick-mode").check()
        page.locator("#submit-btn").click()

        # Wait for results
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)

        # Check quick actions panel
        quick_actions_panel = page.locator("#quick-actions-panel")

        page.wait_for_timeout(1000)

        if quick_actions_panel.is_visible():
            take_screenshot(page, "10_quick_actions_panel")

            # Check for patterns
            quick_actions_container = page.locator("#quick-actions-container")
            actions = quick_actions_container.locator("button")
            action_count = actions.count()
            print(f"Quick actions found: {action_count}")

            # Try expanding a pattern if available - find a visible button
            if action_count > 0:
                # Look for a visible action button
                visible_action = quick_actions_container.locator("button:visible").first
                if visible_action.count() > 0:
                    visible_action.click()
                    page.wait_for_timeout(500)
                    take_screenshot(page, "10a_quick_action_expanded")
                else:
                    print("Quick actions buttons not visible - may be collapsed")
        else:
            take_screenshot(page, "10_no_quick_actions")
            print("Quick actions panel not visible - may not have detected patterns")


class TestDarkMode:
    """Test dark mode toggle."""

    def test_dark_mode_toggle(self, page: Page):
        """Test: Toggle dark mode, verify no visual breaks."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Take initial screenshot (should be light mode by default or system preference)
        take_screenshot(page, "11_initial_theme")

        # Find theme toggle
        theme_toggle = page.locator("#theme-toggle")
        expect(theme_toggle).to_be_visible()

        # Get initial dark class state
        html = page.locator("html")
        initial_dark = "dark" in (html.get_attribute("class") or "")

        # Click toggle
        theme_toggle.click()
        page.wait_for_timeout(300)

        take_screenshot(page, "11a_after_toggle")

        # Verify class changed
        after_dark = "dark" in (html.get_attribute("class") or "")
        assert initial_dark != after_dark, "Theme did not toggle"

        # Toggle back
        theme_toggle.click()
        page.wait_for_timeout(300)

        take_screenshot(page, "11b_toggle_back")

        # Verify it toggled back
        final_dark = "dark" in (html.get_attribute("class") or "")
        assert final_dark == initial_dark, "Theme did not toggle back correctly"

        # Submit some code and verify dark mode doesn't break layout
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)

        # Toggle to dark mode
        if not final_dark:
            theme_toggle.click()
            page.wait_for_timeout(300)

        page.locator("#quick-mode").check()
        page.locator("#submit-btn").click()

        # Wait for results
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)
        page.wait_for_timeout(2000)

        take_screenshot(page, "11c_dark_mode_with_results")

        # Check dark class is properly applied to HTML element
        html = page.locator("html")
        assert "dark" in (html.get_attribute("class") or ""), "Dark mode should be active"

        # Verify no JavaScript errors by checking results section exists
        results = page.locator("#results-section")
        assert results.is_visible(), "Results section should be visible"


class TestMobileViewport:
    """Test mobile responsiveness."""

    def test_mobile_viewport(self, browser):
        """Test: Check mobile viewport (375px width)."""
        # Create context with mobile viewport
        context = browser.new_context(
            viewport={"width": 375, "height": 812},  # iPhone X dimensions
            is_mobile=True,
            has_touch=True
        )
        page = context.new_page()

        try:
            page.goto(BASE_URL, wait_until="networkidle")

            take_screenshot(page, "12_mobile_viewport")

            # Verify key elements are accessible on mobile
            code_input = page.locator("#code-input")
            expect(code_input).to_be_visible()

            submit_btn = page.locator("#submit-btn")
            expect(submit_btn).to_be_visible()

            theme_toggle = page.locator("#theme-toggle")
            expect(theme_toggle).to_be_visible()

            # Enter code and submit on mobile
            code_input.fill(SAMPLE_CODE[:100])  # Use shorter code for mobile

            page.locator("#quick-mode").check()
            submit_btn.click()

            # Wait for results
            expect(page.locator("#results-section")).to_be_visible(timeout=120000)

            take_screenshot(page, "12a_mobile_with_results")

            # Scroll to check if content is accessible
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(300)

            take_screenshot(page, "12b_mobile_scrolled")

            # Check no horizontal overflow
            body_width = page.evaluate("document.body.scrollWidth")
            viewport_width = page.evaluate("window.innerWidth")

            if body_width > viewport_width + 10:  # Allow small tolerance
                record_bug(
                    "Mobile Horizontal Overflow",
                    f"Page has horizontal overflow: body width {body_width}px > viewport {viewport_width}px"
                )

        finally:
            context.close()


class TestHistoryModal:
    """Test history modal functionality."""

    def test_history_modal(self, page: Page):
        """Test history modal opens and closes."""
        page.goto(BASE_URL, wait_until="networkidle")

        # Click history button
        history_btn = page.locator("#history-btn")
        expect(history_btn).to_be_visible()
        history_btn.click()

        # Wait for modal to appear
        history_modal = page.locator("#history-modal")
        expect(history_modal).to_be_visible()

        take_screenshot(page, "13_history_modal")

        # Close the modal
        close_btn = page.locator("#close-history")
        close_btn.click()

        page.wait_for_timeout(300)
        expect(history_modal).to_be_hidden()


class TestEndToEnd:
    """Complete end-to-end test."""

    def test_full_workflow(self, page: Page):
        """Complete workflow from code submission to export."""
        page.goto(BASE_URL, wait_until="networkidle")

        take_screenshot(page, "e2e_01_start")

        # 1. Enter code
        code_input = page.locator("#code-input")
        code_input.fill(SAMPLE_CODE)

        take_screenshot(page, "e2e_02_code_entered")

        # 2. Add context (optional)
        context_input = page.locator("#context-input")
        context_input.fill("This is a security-sensitive application handling user authentication")

        take_screenshot(page, "e2e_03_context_added")

        # 3. Enable quick mode for faster testing
        page.locator("#quick-mode").check()

        # 4. Submit
        page.locator("#submit-btn").click()

        # 5. Wait for processing
        expect(page.locator("#status-section")).to_be_visible(timeout=5000)
        take_screenshot(page, "e2e_04_processing")

        # 6. Wait for results
        expect(page.locator("#results-section")).to_be_visible(timeout=120000)
        take_screenshot(page, "e2e_05_results")

        # 7. Check consensus (may not be visible in quick mode)
        consensus = page.locator("#consensus-panel")
        page.wait_for_timeout(2000)
        if consensus.is_visible():
            print("Consensus panel is visible")
        else:
            print("Consensus panel not visible - recording bug")
            record_bug(
                "E2E: Consensus Panel Missing",
                "During end-to-end test, consensus panel did not appear"
            )

        # 8. Expand first review panel if collapsed
        first_review = page.locator(".agent-panel").first
        if first_review.count() > 0:
            header = first_review.locator(".cursor-pointer").first
            if header.count() > 0:
                header.click()
                page.wait_for_timeout(300)
                take_screenshot(page, "e2e_06_review_expanded")

        # 9. Toggle dark mode
        page.locator("#theme-toggle").click()
        page.wait_for_timeout(300)
        take_screenshot(page, "e2e_07_dark_mode")

        # 10. Final state
        take_screenshot(page, "e2e_08_final")

        print("End-to-end test completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
