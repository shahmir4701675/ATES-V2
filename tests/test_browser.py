"""Phase 1 browser gate against a fresh local database and real HTTPS server."""

from contextlib import contextmanager
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from backend.cli import LOCAL, bootstrap
from backend.data.database import ROOT
from conftest import TEST_PASSWORD, TEST_SECRET


@contextmanager
def running_server(url, tls_dir, *, worker=False):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    address = f"https://127.0.0.1:{port}"
    env = dict(os.environ, ATES_DATABASE_URL=url, ATES_JWT_SECRET=TEST_SECRET, PYTHONPATH=str(ROOT),
               ATES_TEST_START_WORKER="1" if worker else "0")
    with (tls_dir / "server.log").open("w+", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "tests" / "browser_server.py"), str(port), str(tls_dir)],
            cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(150):
                if process.poll() is not None:
                    break
                try:
                    ready = httpx.get(address, verify=False, timeout=.5).status_code == 200
                except httpx.TransportError:
                    ready = False
                if ready:
                    yield address
                    return
                time.sleep(.10)
            output.seek(0)
            pytest.fail("HTTPS test server never became ready.\n" + output.read())
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def browser_sign_in(page, username, password=TEST_PASSWORD):
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Sign in").click()
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def start_account(page, username, name, role, password=TEST_PASSWORD):
    page.get_by_role("button", name="Add account").click()
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Full name", exact=True).fill(name)
    page.get_by_label("Email", exact=True).fill(username + "@example.test")
    page.get_by_label("Role", exact=True).select_option(role)
    page.get_by_label("Initial password", exact=True).fill(password)


def test_FR_1_4_1_6_1_8_SEC_5_UC_01_UC_02_https_browser(migrated_db):
    url = migrated_db.url.render_as_string(hide_password=False)
    bootstrap(url, "admin", "Gate Administrator", "admin@example.test", TEST_PASSWORD)
    artifacts = LOCAL / "evidence" / "phase1"
    artifacts.mkdir(parents=True, exist_ok=True)
    with running_server(url, artifacts) as address, sync_playwright() as playwright:
        channel = os.getenv("ATES_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
        browser = playwright.chromium.launch(channel=channel)
        context = browser.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("pageerror", lambda error: print(f"Browser error: {error}"))
        page.on("console", lambda message: print(message.text) if message.type == "error" else None)
        page.goto(address)
        browser_sign_in(page, "admin")
        assert page.evaluate("window.isSecureContext")
        print(f"Browser {channel} {browser.version} at HTTPS, viewports 1280 and 360")
        page.reload()
        expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
        page.get_by_role("link", name="API reference").click()
        expect(page.locator("#api-reference .swagger-ui")).to_be_visible(timeout=15_000)
        expect(page.get_by_text("Auto Timetable / Exam Scheduler", exact=False)).to_be_visible()
        page.get_by_role("link", name="User accounts").click()
        expect(page.get_by_role("article", name="admin")).to_be_visible()

        start_account(page, "faculty", "Gate Faculty", "Faculty", "1234567")
        page.get_by_label("Instructor", exact=True).select_option("new")
        page.get_by_label("Instructor name", exact=True).fill("Gate Instructor")
        page.get_by_label("Instructor email", exact=True).fill("instructor@example.test")
        page.get_by_label("Department", exact=True).select_option("new")
        page.get_by_label("Department code", exact=True).fill("CS")
        page.get_by_label("Department name", exact=True).fill("Computing")
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_role("alert")).to_contain_text("highlighted fields")
        expect(page.get_by_label("Instructor name", exact=True)).to_have_value("Gate Instructor")
        page.get_by_label("Initial password", exact=True).fill(TEST_PASSWORD)
        page.get_by_role("button", name="Create account").click()
        expect(page.get_by_role("article", name="faculty")).to_be_visible()

        page.set_viewport_size({"width": 360, "height": 800})
        start_account(page, "student", "Gate Student", "Student")
        page.get_by_label("Batch", exact=True).select_option("new")
        page.get_by_label("Programme code", exact=True).fill("CS")
        page.get_by_label("Year", exact=True).fill("2026")
        page.get_by_label("Section", exact=True).fill("A")
        page.get_by_label("Student count", exact=True).fill("27")
        page.get_by_label("Department", exact=True).select_option(label="Computing")
        page.get_by_role("button", name="Create account").click()
        student = page.get_by_role("article", name="student")
        expect(student).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") == 360
        page.screenshot(path=artifacts / "accounts-mobile.png", full_page=True)

        student.get_by_role("button", name="Reset password").click()
        page.get_by_label("New password").fill("reset-only-password")
        page.get_by_role("button", name="Reset password").click()
        expect(page.get_by_role("status")).to_contain_text("Password reset.")
        for username, role in (("coordinator", "Coordinator"), ("approver", "Approver")):
            start_account(page, username, f"Gate {role}", role)
            page.get_by_role("button", name="Create account").click()
            expect(page.get_by_role("article", name=username)).to_be_visible()
        page.get_by_role("button", name="Sign out").click()
        expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
        for username in ("faculty", "student", "coordinator", "approver"):
            browser_sign_in(page, username, "reset-only-password" if username == "student" else TEST_PASSWORD)
            expect(page.get_by_role("heading", name=f"Welcome, Gate {username.title()}")).to_be_visible()
            expect(page.get_by_role("link", name="User accounts")).to_have_count(0)
            status = page.evaluate("""async () => (await fetch('/api/users', {headers: {
              Authorization: 'Bearer ' + sessionStorage.getItem('ates.session')
            }})).status""")
            assert status == 403
            page.evaluate("location.hash = 'users'")
            expect(page.get_by_role("heading", name="Page unavailable")).to_be_visible()
            if username == "student":
                page.get_by_role("link", name="Change password").click()
                page.get_by_label("Current password").fill("reset-only-password")
                page.get_by_label("New password").fill("student-new-password")
                page.get_by_role("button", name="Change password").click()
                expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
                browser_sign_in(page, username, "student-new-password")
            page.get_by_role("button", name="Sign out").click()
            expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
        page.reload()
        expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
        context.close()
        browser.close()

