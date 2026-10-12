#!/usr/bin/env python3
"""
TinDog auto-swipe bot for 100 Days of Python (https://app.100daysofpython.dev/).

Educational Selenium script: platform login → personal TinDog URL → mock Facebark login
→ dismiss teaching popups → click Like until done or MAX_LIKES.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://app.100daysofpython.dev"
LOGIN_URL = f"{BASE_URL}/auth/login"
TINDOG_ADMIN_URL = f"{BASE_URL}/services/tindog/admin/profile"
TINDOG_SWIPE_URL = f"{BASE_URL}/services/tindog"
FACEBARK_LOGIN_URL = f"{BASE_URL}/services/tindog/fb-login"

# Platform login
SELECTOR_PLATFORM_EMAIL = (By.CSS_SELECTOR, "input#email")
SELECTOR_PLATFORM_PASSWORD = (By.CSS_SELECTOR, "input#password")
SELECTOR_PLATFORM_SIGN_IN = (By.CSS_SELECTOR, "button[type='submit']")

SELECTOR_TINDOG_URL_INPUT = (By.CSS_SELECTOR, "input#tindog-url")

# Mock Facebark (any values work on the teaching form)
SELECTOR_FB_EMAIL = (By.CSS_SELECTOR, "input#email")
SELECTOR_FB_PASSWORD = (By.CSS_SELECTOR, "input#pass")
SELECTOR_FB_SUBMIT = (By.CSS_SELECTOR, "form[action*='fb-login'] button[type='submit']")

# Swipe actions (see /js/services/tindog.js — Like appears after a short delay)
SELECTOR_LIKE = (By.CSS_SELECTOR, "button.btn-like")
SELECTOR_NOPE = (By.CSS_SELECTOR, "button.btn-nope")

SELECTOR_POPUP_OVERLAY = (By.CSS_SELECTOR, ".popup-overlay")
SELECTOR_POPUP_SUBMIT = (By.CSS_SELECTOR, "button[type='submit'], button.btn-primary")

SELECTOR_MATCH_OVERLAY = (By.CSS_SELECTOR, ".popup-overlay.popup-match, .popup-match")
SELECTOR_NO_MORE = [
    (By.XPATH, "//*[contains(translate(., 'NO MORE', 'no more'), 'no more')]"),
    (By.XPATH, "//*[contains(translate(., 'OUT OF', 'out of'), 'out of likes')]"),
    (By.CSS_SELECTOR, ".empty-state"),
]


@dataclass
class Settings:
    email: str
    password: str
    facebark_email: str
    facebark_password: str
    headless: bool
    max_likes: int
    pause_seconds: float
    tindog_url: str | None

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        email = os.environ.get("TINDOG_PLATFORM_EMAIL", "").strip()
        password = os.environ.get("TINDOG_PLATFORM_PASSWORD", "").strip()
        if not email or not password:
            raise SystemExit(
                "Set TINDOG_PLATFORM_EMAIL and TINDOG_PLATFORM_PASSWORD "
                "(see .env.example)."
            )
        return cls(
            email=email,
            password=password,
            facebark_email=os.environ.get("FACEBARK_EMAIL", "bot@example.com").strip(),
            facebark_password=os.environ.get("FACEBARK_PASSWORD", "anything").strip(),
            headless=os.environ.get("HEADLESS", "1").strip() not in ("0", "false", "False"),
            max_likes=int(os.environ.get("MAX_LIKES", "50")),
            pause_seconds=float(os.environ.get("PAUSE_SECONDS", "0.8")),
            tindog_url=os.environ.get("TINDOG_URL", "").strip() or None,
        )


def build_driver(headless: bool) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def safe_click(driver: webdriver.Chrome, element) -> None:
    try:
        element.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", element)


def login_platform(driver: webdriver.Chrome, settings: Settings) -> None:
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable(SELECTOR_PLATFORM_EMAIL)
    ).send_keys(settings.email)
    driver.find_element(*SELECTOR_PLATFORM_PASSWORD).send_keys(settings.password)
    safe_click(driver, driver.find_element(*SELECTOR_PLATFORM_SIGN_IN))
    WebDriverWait(driver, 20).until(
        lambda d: "/dashboard" in d.current_url or "/services" in d.current_url
    )


def resolve_tindog_url(driver: webdriver.Chrome, settings: Settings) -> str:
    if settings.tindog_url:
        return settings.tindog_url
    driver.get(TINDOG_ADMIN_URL)
    field = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located(SELECTOR_TINDOG_URL_INPUT)
    )
    url = (field.get_attribute("value") or "").strip()
    if not url:
        raise RuntimeError(
            "Could not read personal TinDog URL. Set TINDOG_URL in your environment."
        )
    return url


def bootstrap_personal_url(driver: webdriver.Chrome, personal_url: str) -> None:
    """Hit the personal URL once so the server ties this browser session to TinDog."""
    driver.get(personal_url)
    WebDriverWait(driver, 15).until(
        lambda d: "/services/tindog" in d.current_url
    )


def login_facebark(driver: webdriver.Chrome, settings: Settings) -> None:
    """Mock Facebark login (opens in the same window — no popup needed for Selenium)."""
    driver.get(FACEBARK_LOGIN_URL)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located(SELECTOR_FB_EMAIL)
    ).send_keys(settings.facebark_email)
    driver.find_element(*SELECTOR_FB_PASSWORD).send_keys(settings.facebark_password)
    safe_click(driver, driver.find_element(*SELECTOR_FB_SUBMIT))
    WebDriverWait(driver, 20).until(
        lambda d: TINDOG_SWIPE_URL in d.current_url and "fb-login" not in d.current_url
    )


def dismiss_teaching_popups(driver: webdriver.Chrome, rounds: int = 8) -> None:
    """Dismiss location / notifications / similar overlays (POST via form buttons)."""
    for _ in range(rounds):
        visible = [
            o
            for o in driver.find_elements(*SELECTOR_POPUP_OVERLAY)
            if o.is_displayed()
        ]
        if not visible:
            return
        overlay = visible[0]
        if "popup-match" in (overlay.get_attribute("class") or ""):
            return
        clicked = False
        for btn in overlay.find_elements(*SELECTOR_POPUP_SUBMIT):
            if btn.is_displayed():
                safe_click(driver, btn)
                clicked = True
                time.sleep(0.6)
                break
        if not clicked:
            return


def dismiss_match_popup(driver: webdriver.Chrome) -> None:
    for overlay in driver.find_elements(*SELECTOR_MATCH_OVERLAY):
        if not overlay.is_displayed():
            continue
        for btn in overlay.find_elements(*SELECTOR_POPUP_SUBMIT):
            text = (btn.text or "").lower()
            if btn.is_displayed() and any(k in text for k in ("keep", "ok", "continue", "close")):
                safe_click(driver, btn)
                time.sleep(0.5)
                return
        for btn in overlay.find_elements(*SELECTOR_POPUP_SUBMIT):
            if btn.is_displayed():
                safe_click(driver, btn)
                time.sleep(0.5)
                return


def out_of_profiles(driver: webdriver.Chrome) -> bool:
    for locator in SELECTOR_NO_MORE:
        for el in driver.find_elements(*locator):
            if el.is_displayed():
                return True
    return False


def wait_for_like_button(driver: webdriver.Chrome, timeout: float = 20):
    """Like button is injected after ~0.6–1.2s (see tindog.js wireDelayedLikeButton)."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(SELECTOR_LIKE)
    )


def auto_like(driver: webdriver.Chrome, settings: Settings) -> int:
    likes = 0
    while likes < settings.max_likes:
        dismiss_teaching_popups(driver)
        dismiss_match_popup(driver)

        if out_of_profiles(driver):
            print("No more profiles (or out of likes). Stopping.")
            break

        try:
            like_btn = wait_for_like_button(driver)
        except TimeoutException:
            dismiss_teaching_popups(driver)
            try:
                like_btn = wait_for_like_button(driver, timeout=5)
            except TimeoutException:
                print("Like button not found. Stopping.")
                break

        try:
            safe_click(driver, like_btn)
            likes += 1
            print(f"Like #{likes}")
            time.sleep(settings.pause_seconds)
            dismiss_match_popup(driver)
            dismiss_teaching_popups(driver)
        except StaleElementReferenceException:
            time.sleep(0.5)
            continue

    return likes


def enter_swipe_view(driver: webdriver.Chrome, settings: Settings) -> None:
    personal = resolve_tindog_url(driver, settings)
    print(f"Personal TinDog URL: {personal[:55]}…")
    bootstrap_personal_url(driver, personal)
    login_facebark(driver, settings)
    dismiss_teaching_popups(driver)


def main() -> int:
    settings = Settings.from_env()
    driver = build_driver(settings.headless)

    try:
        print("Logging into 100 Days of Python…")
        login_platform(driver, settings)

        print("Opening TinDog swipe view…")
        enter_swipe_view(driver, settings)

        total = auto_like(driver, settings)
        print(f"Done. Total likes: {total}")
        return 0
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
