#!/usr/bin/env python3
"""Verify that the public Human Hours legal pages match the disclosure contract."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


POLICY_VERSION = "2026-08-11"
_POLICY_DATE = date.fromisoformat(POLICY_VERSION)
POLICY_UPDATED_STATEMENT = f"Last updated: {_POLICY_DATE.day} {_POLICY_DATE:%B %Y}"

APPROVED_TITLES = {
    "privacy.html": "Human Hours - Privacy Policy",
    "support.html": "Human Hours - Support",
}

APPROVED_META_TAGS = [
    {"charset": "utf-8"},
    {"name": "viewport", "content": "width=device-width, initial-scale=1"},
]

APPROVED_DOCUMENT_SHA256 = {
    "privacy.html": "64ffc311b8c575681fe071915028301badd6e548e40bcae7e5a1446edd007f06",
    "support.html": "ab572da17824c46d211e9bae2bb8309044657c585fc10de8c032cb5e6a48292a",
}

APPROVED_STYLES = {
    "privacy.html": """
        :root { color-scheme: light dark; }
        body { font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
               max-width: 720px; margin: 0 auto; padding: 48px 22px; color: #1c1c1e; }
        h1 { font-size: 28px; margin-bottom: 4px; }
        h2 { font-size: 19px; margin-top: 34px; }
        h3 { font-size: 16px; margin-top: 24px; }
        ul { padding-left: 22px; }
        li + li { margin-top: 8px; }
        .updated { color: #6b6b70; font-size: 14px; margin-top: 0; }
        a { color: #0066cc; }
        @media (prefers-color-scheme: dark) {
          body { background:#000; color:#e8e8ec; }
          a { color: #409cff; }
          .updated { color:#9a9aa0; }
        }
    """,
    "support.html": """
        :root { color-scheme: light dark; }
        body { font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
               max-width: 720px; margin: 0 auto; padding: 48px 22px; color: #1c1c1e; }
        h1 { font-size: 28px; }
        h2 { font-size: 19px; margin-top: 30px; }
        h3 { font-size: 16px; margin-top: 24px; margin-bottom: 2px; }
        a { color: #0066cc; }
        @media (prefers-color-scheme: dark) {
          body { background:#000; color:#e8e8ec; }
          a { color: #409cff; }
        }
    """,
}

REQUIRED_STATEMENTS = {
    "privacy.html": {
        "policy-updated": POLICY_UPDATED_STATEMENT,
        "platform-scope": "This policy covers Human Hours on iOS and Android.",
        "provider": "Human Hours is provided by Anand Sharma.",
        "no-first-party-backend": (
            "Human Hours does not operate an account system or a backend that receives your wellness data."
        ),
        "local-data-categories": (
            "This includes your onboarding answers, appearance and day-start settings, Journal notes and triggers, "
            "Pause outcomes, Flow timing and reflections, Story progress, selected protection rules, and diagnostic "
            "or session history."
        ),
        "ios-screen-time-categories": (
            "Depending on the feature and authorization Apple grants, Human Hours can handle usage and category totals, "
            "app display names, bundle identifiers, opaque Family Controls tokens, selected apps, categories and web "
            "domains, domain names, durations, pickup and notification counts, hourly or daily history, and rule "
            "selections."
        ),
        "ios-no-wellness-egress": (
            "Human Hours does not send Screen Time data, selected app or website identifiers, Journal content, or "
            "protection rules to RevenueCat, analytics services, advertisers, or a Human Hours server."
        ),
        "android-accessibility-consent": (
            "On Android, Mindful Pause is optional and uses an Accessibility Service only after you read the in-app "
            "disclosure, affirmatively consent, and enable the service in Android Settings."
        ),
        "android-foreground-package": (
            "When enabled, the service receives the foreground package name after a window-state change and compares "
            "it locally with the apps you selected."
        ),
        "android-no-screen-content": "The Accessibility Service cannot retrieve screen content.",
        "android-app-inventory": (
            "The app picker queries launchable apps and reads their package names, labels, and icons so you can choose "
            "which apps to protect."
        ),
        "android-unselected-packages": (
            "Human Hours stores selected package identifiers but does not persist package names for unselected "
            "foreground apps."
        ),
        "android-notifications": (
            "Android can ask for notification permission to show an ongoing Flow countdown and completion actions."
        ),
        "android-exact-alarm-check": (
            "On Android versions that require it, Human Hours checks whether exact-alarm access has already been "
            "granted; it does not open the system screen to request that access."
        ),
        "android-exact-alarm-manual-grant": (
            "You can grant Alarms & reminders manually under Android Special app access where that setting is available."
        ),
        "android-alarm-fallback": (
            "If exact-alarm access is unavailable, the system fallback can deliver the completion alert late."
        ),
        "purchase-platforms": (
            "Human Hours Pro is sold through the Apple App Store or Google Play and managed with RevenueCat."
        ),
        "revenuecat-startup": (
            "RevenueCat is initialized during normal app startup or foregrounding so Human Hours can determine whether "
            "Pro is active."
        ),
        "revenuecat-anonymous-id": (
            "Human Hours supplies no custom user identifier, name, or email address to RevenueCat, so the SDK creates "
            "a random anonymous App User ID."
        ),
        "revenuecat-data": (
            "RevenueCat processes purchase history, product, transaction, subscription and entitlement information, "
            "Apple receipts or Google purchase tokens, device and OS information, locale and currency information, and "
            "connection information."
        ),
        "revenuecat-android-paywall-events": (
            "On Android, RevenueCat's prebuilt paywall automatically processes paywall presentation and interaction "
            "events, including impressions, closes, and purchase cancellations."
        ),
        "revenuecat-android-paywall-event-data": (
            "These events include the anonymous App User ID, an event identifier, a paywall session identifier, a "
            "timestamp, the offering identifier and paywall revision, display mode, light or dark appearance, and "
            "locale, and RevenueCat uses them for paywall analytics and functionality."
        ),
        "revenuecat-ip": (
            "RevenueCat documents that it may use a customer's last-seen IP address to determine country when transaction "
            "country is unavailable, and that it drops the raw IP address after determining country."
        ),
        "logical-day-definition": (
            "Where this policy refers to a logical day, it means a day that follows the day-start time you choose in "
            "Human Hours rather than always changing at midnight."
        ),
        "ios-journal-storage-retention": (
            "On iOS, when Journal data is loaded or saved, entries older than a rolling 30-calendar-day window measured "
            "from the current time are removed."
        ),
        "ios-journal-visibility": (
            "The iOS Journal screen shows a rolling 10-calendar-day window on the free plan and the full retained "
            "window on Pro; these Journal windows do not use the logical-day boundary."
        ),
        "ios-intent-retention": "Intent Check history is retained for 8 logical days.",
        "ios-session-retention": (
            "Session and reflection history is retained for 14 days or 200 records, whichever limit is reached first."
        ),
        "ios-diagnostic-retention": "Diagnostic history is capped at 80 entries.",
        "android-journal-storage-retention": (
            "On Android, Journal entries are retained for the current logical day and the preceding 29 logical days."
        ),
        "android-journal-visibility": (
            "The Android Journal screen shows the current logical day and the preceding 9 logical days on the free "
            "plan, and all retained Journal entries on Pro."
        ),
        "android-event-retention": (
            "On Android, Pause and completed Flow history is retained for the current logical day and the preceding 6 "
            "logical days."
        ),
        "ios-backup": (
            "Depending on your Apple settings, this app data can be included in an iCloud Backup or a device backup."
        ),
        "android-backup": (
            "On Android, Human Hours stores state in its private sandbox, excludes it from cloud backup and device "
            "transfer, and disables cleartext network traffic."
        ),
        "ios-delete-not-offload": (
            "To remove other iOS app data, delete Human Hours from the device rather than offloading it, because "
            "offloading can preserve app data."
        ),
        "android-delete": (
            "On Android, Settings > Delete local data removes the primary state and its Human Hours recovery copies."
        ),
        "purchase-cancellation": (
            "Deleting Human Hours or its local data does not cancel a subscription and does not delete purchase records "
            "held by Apple, Google, or RevenueCat."
        ),
    },
    "support.html": {
        "support-context": (
            "Include whether you use iOS or Android, the Human Hours app version, your OS version, and the steps that "
            "reproduce the problem."
        ),
        "support-sensitive-data": (
            "Please do not send Journal notes or sensitive screenshots unless they are necessary to diagnose the problem."
        ),
        "ios-screen-time": "Open Human Hours and allow App Protection when prompted.",
        "ios-mindful-pause": (
            "Open Human Hours Settings > Mindful Pauses and confirm that App Protection is allowed, a rule is enabled, "
            "and the intended app or website is selected."
        ),
        "ios-clear-journal": (
            "Use Human Hours Settings > Clear Journal to delete every local Journal entry."
        ),
        "ios-offload": "Choose Delete App rather than offloading, because offloading can preserve app data.",
        "ios-backup": "Manage any iCloud or device backup copies separately in your Apple backup settings.",
        "android-accessibility-setup": (
            "Open Human Hours Settings > Mindful Pause, review the Accessibility disclosure, turn on consent, and "
            "select the app you want to watch."
        ),
        "android-accessibility-enable": (
            "Then open Android Accessibility settings and enable Human Hours Mindful Pause."
        ),
        "android-no-screen-content": (
            "The service reads only the foreground app name and cannot read screen content."
        ),
        "android-notifications": (
            "Allow notifications for Human Hours in Android Settings > Apps > Human Hours > Notifications."
        ),
        "android-alarm-fallback": (
            "Without notifications or exact alarms, Flow still runs and records locally, but off-screen reminders can "
            "be reduced or late."
        ),
        "android-exact-alarm-manual-grant": (
            "For a prompt end alert, also allow Alarms & reminders under Android Special app access where that setting "
            "is available."
        ),
        "android-no-usage-stats": (
            "The Android companion does not request Usage Stats and is not a port of Apple Screen Time."
        ),
        "android-delete": (
            "Open Human Hours Settings > Delete local data to remove pauses, Journal entries, Flow sessions, Story "
            "progress, settings, and Human Hours recovery copies from that device."
        ),
        "ios-restore": "Use the same Apple Account that owns the active purchase.",
        "android-restore": "Use the same Google account that owns the active purchase.",
        "purchase-cancellation": (
            "Deleting Human Hours, choosing Delete local data, or clearing the Journal does not cancel Pro or erase "
            "store transaction history."
        ),
        "support-privacy-summary": (
            "Human Hours has no account system or backend that receives your wellness data."
        ),
    },
}

FORBIDDEN_STATEMENTS = (
    "everything stays on your device",
    "never transmitted to us or to anyone else",
    "no name, email, or ip address is collected",
    "only ever watches the apps you pick",
    "app limits aren't blocking apps",
    "your screen time and journal data stay on your device and are never sent to us",
    "it can also ask for access to exact alarms so the selected flow end time can be announced promptly",
    "revenuecat is used only for purchase receipt and entitlement handling",
)

REQUIRED_LINKS = {
    "privacy.html": {
        "mailto:anandvsharma@icloud.com": "anandvsharma@icloud.com",
        "https://www.apple.com/legal/privacy/": "Apple Privacy Policy",
        "https://policies.google.com/privacy": "Google Privacy Policy",
        "https://www.revenuecat.com/privacy": "Privacy Policy",
        "https://www.revenuecat.com/docs/dashboard-and-metrics/customer-profile": (
            "Customer Profile documentation"
        ),
        "https://www.revenuecat.com/docs/getting-started/tracking-custom-paywall-impressions": (
            "automatic paywall impression guidance"
        ),
        "https://www.revenuecat.com/docs/integrations/webhooks/event-types-and-fields": (
            "paywall event reference"
        ),
        "https://www.revenuecat.com/docs/platform-resources/apple-platform-resources/apple-app-privacy": (
            "Apple App Privacy guidance"
        ),
    },
    "support.html": {
        "mailto:anandvsharma@icloud.com": "anandvsharma@icloud.com",
        "privacy.html": "Privacy Policy",
        "https://apps.apple.com/account/subscriptions": "Apple App Store subscriptions",
        "https://play.google.com/store/account/subscriptions": "Google Play subscriptions",
    },
}

EXPECTED_DOCS_ROOT_ENTRIES = {".nojekyll", *REQUIRED_STATEMENTS}

PROHIBITED_MARKUP = {
    "script element": re.compile(r"<\s*script\b", re.IGNORECASE),
    "template element": re.compile(r"<\s*template\b", re.IGNORECASE),
    "active or embedded element": re.compile(
        r"<\s*(?:base|iframe|object|embed|form|input|button|img|svg|math|video|audio)\b",
        re.IGNORECASE,
    ),
    "meta refresh": re.compile(
        r"<\s*meta\b[^>]*\bhttp-equiv\s*=\s*['\"]?refresh\b",
        re.IGNORECASE,
    ),
    "inline event handler": re.compile(r"<[^>]+\son[a-z]+\s*=", re.IGNORECASE),
    "external stylesheet": re.compile(
        r"<\s*link\b[^>]*\brel\s*=\s*['\"]?stylesheet\b",
        re.IGNORECASE,
    ),
    "CSS external resource": re.compile(r"(?:@import\b|url\s*\()", re.IGNORECASE),
    "inline style attribute": re.compile(r"<[^>]+\sstyle\s*=", re.IGNORECASE),
    "hidden attribute": re.compile(r"<[^>]+\s(?:hidden|aria-hidden)\s*(?:=|\s|>)", re.IGNORECASE),
    "display none": re.compile(r"display\s*:\s*none", re.IGNORECASE),
    "hidden visibility": re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE),
    "transparent text": re.compile(r"color\s*:\s*transparent", re.IGNORECASE),
    "off-screen positioning": re.compile(r"position\s*:\s*(?:absolute|fixed)", re.IGNORECASE),
    "negative displacement": re.compile(
        r"(?:left|right|top|bottom|margin(?:-[a-z]+)?|text-indent)\s*:\s*-",
        re.IGNORECASE,
    ),
    "content clipping": re.compile(r"(?:clip|clip-path)\s*:", re.IGNORECASE),
    "content transform": re.compile(r"transform\s*:", re.IGNORECASE),
    "zero opacity": re.compile(
        r"opacity\s*:\s*0(?:\.0+)?(?=\s*(?:[;}\"']|$))",
        re.IGNORECASE,
    ),
    "zero font size": re.compile(
        r"font-size\s*:\s*0(?:\.0+)?(?:[a-z%]+)?(?=\s*(?:[;}\"']|$))",
        re.IGNORECASE,
    ),
}

ALLOWED_TAG_ATTRIBUTES = {
    "html": {"lang"},
    "head": set(),
    "meta": {"charset", "name", "content"},
    "title": set(),
    "style": set(),
    "body": {"data-policy-version"},
    "h1": {"id"},
    "h2": {"id"},
    "h3": {"id"},
    "p": {"class", "data-fact-id", "id"},
    "ul": {"id"},
    "li": {"data-fact-id", "id"},
    "a": {"href", "id"},
}

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def normalize(value: str) -> str:
    canonical = value.lower().translate(str.maketrans({"’": "'", "›": ">"}))
    return " ".join(canonical.split())


def normalize_stylesheet(value: str) -> str:
    return " ".join(value.split())


@dataclass
class ParsedLink:
    href: str
    text_parts: list[str] = field(default_factory=list)

    @property
    def visible_text(self) -> str:
        return normalize(" ".join(self.text_parts))


@dataclass
class ParsedDocument:
    text_parts: list[str] = field(default_factory=list)
    links: set[str] = field(default_factory=set)
    link_occurrences: list[ParsedLink] = field(default_factory=list)
    element_ids: set[str] = field(default_factory=set)
    fact_text_parts: dict[str, list[str]] = field(default_factory=dict)
    fact_counts: dict[str, int] = field(default_factory=dict)
    style_blocks: list[str] = field(default_factory=list)
    declarations: list[str] = field(default_factory=list)
    html_languages: list[str | None] = field(default_factory=list)
    meta_tags: list[dict[str, str | None]] = field(default_factory=list)
    title_blocks: list[str] = field(default_factory=list)
    parser_errors: list[str] = field(default_factory=list)
    policy_version: str | None = None

    @property
    def visible_text(self) -> str:
        return normalize(" ".join(self.text_parts))


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document = ParsedDocument()
        self._inside_body = False
        self._seen_body = False
        self._element_stack: list[tuple[str, bool, str | None, int | None]] = []

    @property
    def _inside_hidden_element(self) -> bool:
        return bool(self._element_stack and self._element_stack[-1][1])

    @property
    def _inside_head(self) -> bool:
        return any(tag == "head" for tag, _, _, _ in self._element_stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes: dict[str, str | None] = {}
        for name, value in attrs:
            if name in attributes:
                self.document.parser_errors.append(f"duplicate attribute on <{tag}>: {name}")
                continue
            attributes[name] = value

        allowed_attributes = ALLOWED_TAG_ATTRIBUTES.get(tag)
        if allowed_attributes is None:
            self.document.parser_errors.append(f"unsupported HTML element: <{tag}>")
        else:
            for name in sorted(set(attributes) - allowed_attributes):
                self.document.parser_errors.append(f"unsupported attribute on <{tag}>: {name}")

        if tag == "p" and "class" in attributes and attributes["class"] != "updated":
            self.document.parser_errors.append(
                f"unsupported class on <p>: {attributes['class'] or 'empty'}"
            )

        if tag == "html":
            self.document.html_languages.append(attributes.get("lang"))
        elif tag == "meta":
            self.document.meta_tags.append(attributes.copy())
        elif tag == "title":
            self.document.title_blocks.append("")

        parent_tag = self._element_stack[-1][0] if self._element_stack else None
        if tag == "html" and parent_tag is not None:
            self.document.parser_errors.append("<html> must be the document root")
        elif tag == "head" and parent_tag != "html":
            self.document.parser_errors.append("<head> must be a direct child of <html>")
        elif tag in {"meta", "title", "style"} and not self._inside_head:
            self.document.parser_errors.append(f"<{tag}> must be inside <head>")
        elif tag == "body":
            if parent_tag != "html":
                self.document.parser_errors.append("<body> must be a direct child of <html>")
            if self._seen_body:
                self.document.parser_errors.append("document must contain only one <body>")
        elif tag not in {"html", "head", "meta", "title", "style"} and not self._inside_body:
            self.document.parser_errors.append(f"<{tag}> must be inside <body>")

        parent_fact_id = self._element_stack[-1][2] if self._element_stack else None
        parent_link_index = self._element_stack[-1][3] if self._element_stack else None
        own_fact_id = attributes.get("data-fact-id")
        effective_fact_id = own_fact_id or parent_fact_id
        if own_fact_id:
            self.document.fact_counts[own_fact_id] = self.document.fact_counts.get(own_fact_id, 0) + 1
            self.document.fact_text_parts.setdefault(own_fact_id, [])

        parent_hidden = self._inside_hidden_element
        own_hidden = (
            tag in {"head", "script", "style", "template", "title", "noscript"}
            or "hidden" in attributes
            or normalize(attributes.get("aria-hidden") or "") == "true"
        )
        effective_hidden = parent_hidden or own_hidden

        if tag == "body":
            self._inside_body = True
            self._seen_body = True
            self.document.policy_version = attributes.get("data-policy-version")

        if tag == "style":
            self.document.style_blocks.append("")

        active_link_index = parent_link_index
        if self._inside_body and not effective_hidden:
            if attributes.get("id"):
                self.document.element_ids.add(attributes["id"] or "")
            if tag == "a" and attributes.get("href"):
                href = attributes["href"] or ""
                self.document.links.add(href)
                active_link_index = len(self.document.link_occurrences)
                self.document.link_occurrences.append(ParsedLink(href=href))

        if tag not in VOID_TAGS:
            self._element_stack.append((tag, effective_hidden, effective_fact_id, active_link_index))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self._pop_through(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self._pop_through(tag):
            self.document.parser_errors.append(f"unmatched closing element: </{tag}>")
        if tag == "body":
            self._inside_body = False

    def handle_data(self, data: str) -> None:
        if self._element_stack and self._element_stack[-1][0] == "style":
            self.document.style_blocks[-1] += data
        if self._element_stack and self._element_stack[-1][0] == "title":
            self.document.title_blocks[-1] += data
        if self._inside_body and not self._inside_hidden_element:
            self.document.text_parts.append(data)
            fact_id = self._element_stack[-1][2] if self._element_stack else None
            if fact_id:
                self.document.fact_text_parts.setdefault(fact_id, []).append(data)
            link_index = self._element_stack[-1][3] if self._element_stack else None
            if link_index is not None:
                self.document.link_occurrences[link_index].text_parts.append(data)
        elif data.strip() and not self._inside_head:
            self.document.parser_errors.append("non-whitespace text appears outside <body>")

    def handle_decl(self, decl: str) -> None:
        self.document.declarations.append(normalize(decl))

    def _pop_through(self, tag: str) -> bool:
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == tag:
                del self._element_stack[index:]
                return True
        return False


def parse_document(path: Path) -> tuple[ParsedDocument, str]:
    source = path.read_text(encoding="utf-8")
    parser = DocumentParser()
    parser.feed(source)
    parser.close()
    if parser._element_stack:
        parser.document.parser_errors.append(
            "unclosed HTML elements: "
            + ", ".join(f"<{tag}>" for tag, _, _, _ in parser._element_stack)
        )
    return parser.document, source


def markup_errors(file_name: str, source: str) -> list[str]:
    return [
        f"{file_name}: prohibited hidden-content mechanism: {name}"
        for name, pattern in PROHIBITED_MARKUP.items()
        if pattern.search(source)
    ]


def stylesheet_errors(file_name: str, document: ParsedDocument) -> list[str]:
    if len(document.style_blocks) != 1:
        return [f"{file_name}: expected exactly one embedded stylesheet"]
    if normalize_stylesheet(document.style_blocks[0]) != normalize_stylesheet(APPROVED_STYLES[file_name]):
        return [f"{file_name}: embedded stylesheet differs from the reviewed stylesheet"]
    return []


def head_errors(file_name: str, document: ParsedDocument) -> list[str]:
    errors: list[str] = []
    if document.declarations != ["doctype html"]:
        errors.append(f"{file_name}: document must have exactly one HTML5 doctype")
    if document.html_languages != ["en"]:
        errors.append(f'{file_name}: document must have exactly one <html lang="en"> root')
    if document.meta_tags != APPROVED_META_TAGS:
        errors.append(f"{file_name}: head metadata differs from the reviewed metadata")
    if document.title_blocks != [APPROVED_TITLES[file_name]]:
        errors.append(f"{file_name}: title differs from the reviewed title")
    return errors


def statement_errors(file_name: str, document: ParsedDocument) -> list[str]:
    errors: list[str] = []
    expected_statements = REQUIRED_STATEMENTS[file_name]

    for statement_id, statement in expected_statements.items():
        count = document.fact_counts.get(statement_id, 0)
        if count != 1:
            errors.append(
                f"{file_name}: expected one visible fact element for {statement_id}, found {count}"
            )
            continue
        actual = normalize(" ".join(document.fact_text_parts.get(statement_id, [])))
        if actual != normalize(statement):
            errors.append(
                f"{file_name}: fact {statement_id} differs from the approved statement: {statement}"
            )

    for statement_id in sorted(set(document.fact_counts) - set(expected_statements)):
        errors.append(f"{file_name}: unknown fact identifier: {statement_id}")

    return errors


def document_for_link(path: Path) -> ParsedDocument:
    document, _ = parse_document(path)
    return document


def link_errors(
    document: ParsedDocument,
    path: Path,
    docs_root: Path,
) -> list[str]:
    errors: list[str] = []
    expected_links = REQUIRED_LINKS[path.name]

    for link in sorted(set(expected_links) - document.links):
        errors.append(f"{path.name}: missing required link: {link}")

    for occurrence in document.link_occurrences:
        expected_label = expected_links.get(occurrence.href)
        if expected_label is not None and occurrence.visible_text != normalize(expected_label):
            errors.append(
                f"{path.name}: link label differs from the reviewed label for {occurrence.href}: "
                f"expected {expected_label}"
            )

    for link in sorted(document.links):
        if "\\" in link:
            errors.append(f"{path.name}: link contains a browser path separator: {link}")
            continue
        parsed = urlparse(link)
        if parsed.scheme in {"https", "mailto"}:
            if link not in expected_links:
                errors.append(f"{path.name}: unapproved external link: {link}")
            continue
        if parsed.scheme or parsed.netloc:
            errors.append(f"{path.name}: unsupported link scheme: {link}")
            continue
        target = path if not parsed.path else path.parent / unquote(parsed.path)
        resolved_target = target.resolve()
        try:
            resolved_target.relative_to(docs_root.resolve())
        except ValueError:
            errors.append(f"{path.name}: local link escapes the published docs root: {link}")
            continue

        if link not in expected_links:
            errors.append(f"{path.name}: unapproved local link: {link}")
            continue

        if not resolved_target.is_file():
            errors.append(f"{path.name}: broken local link: {link}")
            continue

        if parsed.fragment:
            target_document = document if resolved_target == path.resolve() else document_for_link(resolved_target)
            if unquote(parsed.fragment) not in target_document.element_ids:
                errors.append(f"{path.name}: broken local link fragment: {link}")

    return errors


def verify_document(path: Path, docs_root: Path) -> list[str]:
    errors: list[str] = []
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(docs_root.resolve())
    except ValueError:
        return [f"{path.name}: document escapes the published docs root"]

    document, source = parse_document(path)
    visible_text = document.visible_text

    actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_digest != APPROVED_DOCUMENT_SHA256[path.name]:
        errors.append(f"{path.name}: document bytes differ from the reviewed document")

    errors.extend(f"{path.name}: {error}" for error in document.parser_errors)

    errors.extend(statement_errors(path.name, document))

    for statement in FORBIDDEN_STATEMENTS:
        if normalize(statement) in visible_text:
            errors.append(f"{path.name}: forbidden categorical claim: {statement}")

    errors.extend(markup_errors(path.name, source))
    errors.extend(head_errors(path.name, document))
    errors.extend(stylesheet_errors(path.name, document))
    errors.extend(link_errors(document, path, docs_root))

    if path.name == "privacy.html" and document.policy_version != POLICY_VERSION:
        errors.append(
            f"privacy.html: expected data-policy-version={POLICY_VERSION}, "
            f"found {document.policy_version or 'none'}"
        )

    return errors


def verify_docs(docs_root: Path) -> list[str]:
    if docs_root.is_symlink():
        return [f"published docs root must not be a symbolic link: {docs_root}"]

    errors: list[str] = []
    actual_entries = {
        candidate.relative_to(docs_root).as_posix()
        for candidate in docs_root.rglob("*")
    }
    for entry in sorted(actual_entries - EXPECTED_DOCS_ROOT_ENTRIES):
        errors.append(f"unexpected published docs entry: {entry}")
    for entry in sorted(EXPECTED_DOCS_ROOT_ENTRIES - actual_entries):
        errors.append(f"missing required published docs entry: {entry}")

    nojekyll = docs_root / ".nojekyll"
    if nojekyll.is_symlink() or not nojekyll.is_file():
        errors.append(f"required static-pages marker is not a regular file: {nojekyll}")
    elif nojekyll.read_bytes() != b"\n":
        errors.append(f"required static-pages marker has unexpected content: {nojekyll}")

    for file_name in REQUIRED_STATEMENTS:
        path = docs_root / file_name
        if path.is_symlink():
            errors.append(f"required document must not be a symbolic link: {path}")
            continue
        if not path.is_file():
            errors.append(f"missing required document: {path}")
            continue
        errors.extend(verify_document(path, docs_root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs",
    )
    args = parser.parse_args()
    errors = verify_docs(args.docs_dir)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Verified {len(REQUIRED_STATEMENTS)} legal documents at policy version {POLICY_VERSION}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
