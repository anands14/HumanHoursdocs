from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROPOSED_DOCS_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "proposed_docs"
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.verify_docs import (  # noqa: E402
    DocumentParser,
    ParsedDocument,
    ParsedLink,
    REQUIRED_LINKS,
    link_errors,
    markup_errors,
    normalize,
    parse_document,
    statement_errors,
    stylesheet_errors,
    verify_docs,
)


class WorkflowSecurityTests(unittest.TestCase):
    def test_untrusted_checkout_is_anchored_to_the_docs_directory(self) -> None:
        workflow = (
            REPOSITORY_ROOT / ".github" / "workflows" / "docs-content.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("sparse-checkout-cone-mode: false", workflow)
        self.assertRegex(workflow, r"sparse-checkout: \|\n\s+/docs/\n")
        self.assertNotRegex(workflow, r"sparse-checkout:\s*docs\s*$")


class DocumentParserTests(unittest.TestCase):
    def test_only_visible_body_content_satisfies_the_parser(self) -> None:
        parser = DocumentParser()
        parser.feed(
            """
            <html>
              <head><title>Head-only claim</title><style>.hidden { display: block; }</style></head>
              <body>
                <p>Visible statement</p>
                <div hidden><a href="hidden.html">Hidden statement</a></div>
                <template>Template statement</template>
                <a id="visible-id" href="privacy.html">Visible link</a>
              </body>
            </html>
            """
        )

        self.assertEqual(parser.document.visible_text, "visible statement visible link")
        self.assertEqual(parser.document.links, {"privacy.html"})
        self.assertEqual(parser.document.element_ids, {"visible-id"})

    def test_prohibited_hiding_mechanisms_are_rejected(self) -> None:
        source = (
            '<body><p aria-hidden="true" style="display: none; opacity: 0; font-size: 0px">'
            "Required statement</p></body>"
        )

        errors = markup_errors("privacy.html", source)

        self.assertTrue(any("hidden attribute" in error for error in errors))
        self.assertTrue(any("display none" in error for error in errors))
        self.assertTrue(any("zero opacity" in error for error in errors))
        self.assertTrue(any("zero font size" in error for error in errors))

    def test_active_markup_and_off_screen_css_are_rejected(self) -> None:
        source = (
            '<base href="https://evil.example/"><body onload="hide()">'
            '<style>p { position: absolute; left: -10000vw; }</style>'
            "<p>Required statement</p></body>"
        )

        errors = markup_errors("privacy.html", source)

        self.assertTrue(any("active or embedded element" in error for error in errors))
        self.assertTrue(any("inline event handler" in error for error in errors))
        self.assertTrue(any("off-screen positioning" in error for error in errors))
        self.assertTrue(any("negative displacement" in error for error in errors))

    def test_visible_fractional_opacity_is_not_treated_as_hidden(self) -> None:
        source = '<body><p style="opacity: 0.5; font-size: 0.875rem">Visible statement</p></body>'

        errors = markup_errors("privacy.html", source)

        self.assertFalse(any("zero opacity" in error for error in errors))
        self.assertFalse(any("zero font size" in error for error in errors))

    def test_negated_vocabulary_does_not_equal_an_approved_statement(self) -> None:
        negated = normalize("We never create a random anonymous App User ID.")
        approved = normalize(
            "Human Hours supplies no custom user identifier, name, or email address to RevenueCat, so the SDK "
            "creates a random anonymous App User ID."
        )

        self.assertNotIn(approved, negated)

    def test_duplicate_attributes_are_rejected_and_first_value_is_preserved(self) -> None:
        parser = DocumentParser()
        parser.feed(
            '<body><a href="https://evil.example" href="privacy.html">Privacy</a></body>'
        )

        self.assertEqual(parser.document.links, {"https://evil.example"})
        self.assertTrue(any("duplicate attribute" in error for error in parser.document.parser_errors))

    def test_title_metadata_inside_body_cannot_satisfy_visible_content(self) -> None:
        parser = DocumentParser()
        parser.feed(
            '<html><head><title>Real title</title></head><body>'
            '<title><a href="privacy.html">Hidden privacy link</a></title>'
            "</body></html>"
        )

        self.assertEqual(parser.document.visible_text, "")
        self.assertEqual(parser.document.links, set())
        self.assertTrue(any("<title> must be inside <head>" in error for error in parser.document.parser_errors))

    def test_unreviewed_stylesheet_cannot_hide_approved_facts(self) -> None:
        document = ParsedDocument(style_blocks=["p { filter: opacity(0); }"])

        errors = stylesheet_errors("privacy.html", document)

        self.assertTrue(any("differs from the reviewed stylesheet" in error for error in errors))

    def test_platform_fact_must_keep_its_exact_scoped_statement(self) -> None:
        document, _ = parse_document(PROPOSED_DOCS_ROOT / "privacy.html")
        document.fact_text_parts["android-journal-storage-retention"] = [
            "On Android, Journal entries are retained for a rolling 30-calendar-day window."
        ]

        errors = statement_errors("privacy.html", document)

        self.assertTrue(any("android-journal-storage-retention" in error for error in errors))


class LinkValidationTests(unittest.TestCase):
    def test_required_link_needs_a_visible_label(self) -> None:
        document = ParsedDocument(
            links={"privacy.html"},
            link_occurrences=[ParsedLink(href="privacy.html", text_parts=["   "])],
        )

        errors = link_errors(document, REPOSITORY_ROOT / "docs" / "support.html", REPOSITORY_ROOT / "docs")

        self.assertTrue(any("link label differs" in error for error in errors))

    def test_local_link_cannot_escape_the_published_docs_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            docs_root = root / "docs"
            docs_root.mkdir()
            source_path = docs_root / "support.html"
            source_path.write_text("<body></body>", encoding="utf-8")
            (root / "outside.html").write_text("outside", encoding="utf-8")
            document = ParsedDocument(links={"../outside.html"})

            errors = link_errors(document, source_path, docs_root)

        self.assertTrue(any("escapes the published docs root" in error for error in errors))

    def test_local_link_fragment_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_root = Path(temporary_directory)
            source_path = docs_root / "support.html"
            source_path.write_text('<body><h1 id="known">Support</h1></body>', encoding="utf-8")
            document = ParsedDocument(
                links={"#known", "#missing"},
                element_ids={"known"},
            )

            original_links = REQUIRED_LINKS["support.html"]
            REQUIRED_LINKS["support.html"] = {"#known": "Known", "#missing": "Missing"}
            try:
                errors = link_errors(document, source_path, docs_root)
            finally:
                REQUIRED_LINKS["support.html"] = original_links

        self.assertFalse(any("#known" in error for error in errors))
        self.assertTrue(any("#missing" in error for error in errors))

    def test_unreviewed_same_origin_page_cannot_be_linked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_root = Path(temporary_directory)
            source_path = docs_root / "support.html"
            source_path.write_text("<body></body>", encoding="utf-8")
            (docs_root / "extra.html").write_text("<body>Unreviewed</body>", encoding="utf-8")
            document = ParsedDocument(links={"extra.html"})

            errors = link_errors(document, source_path, docs_root)

        self.assertTrue(any("unapproved local link" in error for error in errors))

    def test_browser_backslash_cannot_bypass_traversal_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            docs_root = root / "docs"
            docs_root.mkdir()
            source_path = docs_root / "support.html"
            source_path.write_text("<body></body>", encoding="utf-8")
            (docs_root / "..\\outside.html").write_text("outside", encoding="utf-8")
            document = ParsedDocument(links={"..\\outside.html"})

            errors = link_errors(document, source_path, docs_root)

        self.assertTrue(any("browser path separator" in error for error in errors))


class RepositoryContractTests(unittest.TestCase):
    def verify_mutated_repository(self, mutation: Callable[[Path], None]) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_root = Path(temporary_directory) / "docs"
            shutil.copytree(PROPOSED_DOCS_ROOT, docs_root)
            mutation(docs_root)
            return verify_docs(docs_root)

    def test_negated_tagged_fact_fails_the_repository_contract(self) -> None:
        def mutate(docs_root: Path) -> None:
            path = docs_root / "privacy.html"
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    "Human Hours supplies no custom user identifier",
                    "It is false that Human Hours supplies no custom user identifier",
                    1,
                ),
                encoding="utf-8",
            )

        errors = self.verify_mutated_repository(mutate)

        self.assertTrue(any("approved complete disclosure pair" in error for error in errors))

    def test_untagged_contradiction_fails_the_repository_contract(self) -> None:
        def mutate(docs_root: Path) -> None:
            path = docs_root / "privacy.html"
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    "<h2>Wellness data handled locally</h2>",
                    "<p>Correction: Human Hours does operate an account system and a backend that receives your "
                    "wellness data.</p>\n<h2>Wellness data handled locally</h2>",
                    1,
                ),
                encoding="utf-8",
            )

        errors = self.verify_mutated_repository(mutate)

        self.assertTrue(any("approved complete disclosure pair" in error for error in errors))

    def test_trailing_browser_body_text_fails_the_repository_contract(self) -> None:
        def mutate(docs_root: Path) -> None:
            path = docs_root / "privacy.html"
            path.write_text(
                path.read_text(encoding="utf-8") + "Correction: unreviewed trailing disclosure.\n",
                encoding="utf-8",
            )

        errors = self.verify_mutated_repository(mutate)

        self.assertTrue(any("approved complete disclosure pair" in error for error in errors))

    def test_hidden_fact_stylesheet_fails_the_repository_contract(self) -> None:
        def mutate(docs_root: Path) -> None:
            path = docs_root / "privacy.html"
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace("h1 {", "p { filter: opacity(0); }\n        h1 {", 1),
                encoding="utf-8",
            )

        errors = self.verify_mutated_repository(mutate)

        self.assertTrue(any("approved complete disclosure pair" in error for error in errors))

    def test_visible_policy_date_is_derived_from_the_policy_version(self) -> None:
        def mutate(docs_root: Path) -> None:
            path = docs_root / "privacy.html"
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace("Last updated: 11 August 2026", "Last updated: 10 August 2026", 1),
                encoding="utf-8",
            )

        errors = self.verify_mutated_repository(mutate)

        self.assertTrue(any("approved complete disclosure pair" in error for error in errors))

    def test_unreviewed_head_metadata_fails_the_repository_contract(self) -> None:
        def mutate(docs_root: Path) -> None:
            path = docs_root / "privacy.html"
            source = path.read_text(encoding="utf-8")
            path.write_text(
                source.replace(
                    '<meta name="viewport" content="width=device-width, initial-scale=1">',
                    '<meta name="viewport" content="width=10000"><meta name="robots" content="noindex">',
                    1,
                ).replace(
                    "<title>Human Hours - Privacy Policy</title>",
                    "<title>Unreviewed title</title>",
                    1,
                ),
                encoding="utf-8",
            )

        errors = self.verify_mutated_repository(mutate)

        self.assertTrue(any("approved complete disclosure pair" in error for error in errors))

    def test_unreviewed_file_cannot_be_published(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            docs_root = Path(temporary_directory)
            (docs_root / "phish.md").write_text("<script>steal()</script>", encoding="utf-8")

            errors = verify_docs(docs_root)

        self.assertTrue(any("unexpected published docs entry" in error for error in errors))

    def test_published_docs_root_cannot_redirect_to_trusted_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            trusted_docs = root / "trusted-docs"
            trusted_docs.mkdir()
            redirected_docs = root / "candidate-docs"
            redirected_docs.symlink_to(trusted_docs, target_is_directory=True)

            errors = verify_docs(redirected_docs)

        self.assertTrue(any("root must not be a symbolic link" in error for error in errors))

    def test_repository_documents_satisfy_the_contract(self) -> None:
        self.assertEqual(verify_docs(REPOSITORY_ROOT / "docs"), [])

    def test_proposed_documents_satisfy_the_full_contract(self) -> None:
        self.assertEqual(verify_docs(PROPOSED_DOCS_ROOT), [])

    def test_proposed_documents_are_routed_through_document_verification(self) -> None:
        with patch("scripts.verify_docs.verify_document", return_value=[]) as verify_document:
            errors = verify_docs(PROPOSED_DOCS_ROOT)

        self.assertEqual(errors, [])
        self.assertEqual(verify_document.call_count, 2)

    def test_legacy_documents_return_after_the_atomic_pair_check(self) -> None:
        with patch("scripts.verify_docs.verify_document", return_value=[]) as verify_document:
            errors = verify_docs(REPOSITORY_ROOT / "docs")

        self.assertEqual(errors, [])
        verify_document.assert_not_called()

    def test_legacy_documents_require_the_exact_published_root(self) -> None:
        mutations = (
            ("extra file", lambda root: (root / "extra.md").write_text("extra", encoding="utf-8")),
            (
                "changed marker",
                lambda root: (root / ".nojekyll").write_text("changed\n", encoding="utf-8"),
            ),
        )
        for name, mutation in mutations:
            with self.subTest(mutation=name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    docs_root = Path(temporary_directory) / "docs"
                    shutil.copytree(REPOSITORY_ROOT / "docs", docs_root)
                    mutation(docs_root)

                    errors = verify_docs(docs_root)

                self.assertNotEqual(errors, [])

    def test_mixed_document_pairs_are_rejected(self) -> None:
        combinations = (
            (REPOSITORY_ROOT / "docs", PROPOSED_DOCS_ROOT, "support.html"),
            (PROPOSED_DOCS_ROOT, REPOSITORY_ROOT / "docs", "support.html"),
        )
        for base_root, replacement_root, replacement_name in combinations:
            with self.subTest(base=base_root, replacement=replacement_root):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    docs_root = Path(temporary_directory) / "docs"
                    shutil.copytree(base_root, docs_root)
                    shutil.copyfile(
                        replacement_root / replacement_name,
                        docs_root / replacement_name,
                    )

                    errors = verify_docs(docs_root)

                self.assertTrue(
                    any("approved complete disclosure pair" in error for error in errors)
                )

    def test_each_approved_document_rejects_a_byte_mutation(self) -> None:
        for source_root in (REPOSITORY_ROOT / "docs", PROPOSED_DOCS_ROOT):
            for file_name in ("privacy.html", "support.html"):
                with self.subTest(source=source_root, file=file_name):
                    with tempfile.TemporaryDirectory() as temporary_directory:
                        docs_root = Path(temporary_directory) / "docs"
                        shutil.copytree(source_root, docs_root)
                        path = docs_root / file_name
                        path.write_bytes(path.read_bytes() + b" ")

                        errors = verify_docs(docs_root)

                    self.assertTrue(
                        any("approved complete disclosure pair" in error for error in errors)
                    )


if __name__ == "__main__":
    unittest.main()
