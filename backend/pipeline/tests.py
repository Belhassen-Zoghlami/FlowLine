import io
import zipfile
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from accounts.models import Developer
from .models import Problem, Repository, Run
from .pipeline import extract_entries, process_run


class ArchiveTests(SimpleTestCase):
    def _archive(self, entries):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for name, text in entries:
                zf.writestr(name, text)
        return buffer.getvalue()

    def test_extracts_text_entries(self):
        archive = self._archive(
            [("1_Build/2_Test.txt", "npm ERR! code E404")]
        )

        self.assertEqual(
            extract_entries(archive),
            [("1_Build/2_Test.txt", "npm ERR! code E404")],
        )

    def test_skips_directories(self):
        archive = self._archive(
            [("1_Build/", ""), ("1_Build/2_Test.txt", "failure")]
        )

        self.assertEqual(
            extract_entries(archive),
            [("1_Build/2_Test.txt", "failure")],
        )

    def test_bad_archive(self):
        self.assertEqual(extract_entries(b"not a zip"), [])
        self.assertEqual(extract_entries(b""), [])


class PipelineTests(TestCase):
    def setUp(self):
        self.developer = Developer.objects.create(
            firebase_uid="test-uid",
            email="test@example.com",
            display_name="Test User",
        )
        self.repository = Repository.objects.create(
            owner=self.developer,
            github_name="acme/app",
        )

    def _run(self, run_id):
        return Run.objects.create(
            repository=self.repository,
            github_run_id=run_id,
            run_number=run_id,
        )

    def _entries(self, line):
        return [("1_Build/2_Test.txt", line)]

    def _embed(self, text):
        if "npm" in text:
            return [1.0, 0.0]
        if "syntax" in text:
            return [0.0, 1.0]
        return [0.6, 0.8]

    @patch("pipeline.grouping.embed_text")
    def test_parsed_run_creates_problem(self, embed_text):
        embed_text.side_effect = self._embed
        run = self._run(1)

        parsed, problem = process_run(
            run, self._entries("npm ERR! code E404")
        )

        self.assertTrue(parsed.is_parsed)
        self.assertEqual(parsed.signature, "npm err! code e404")
        self.assertEqual(parsed.failed_step, "Test")
        self.assertEqual(run.signature, parsed.signature)
        self.assertEqual(run.failed_step, "Test")
        self.assertIsNotNone(problem)
        self.assertEqual(run.problem_id, problem.pk)
        self.assertEqual(problem.num_occurrences, 1)

    @patch("pipeline.grouping.embed_text")
    def test_same_signature_reuses_problem(self, embed_text):
        embed_text.side_effect = self._embed
        first_run = self._run(1)
        _, first_problem = process_run(
            first_run, self._entries("npm ERR! code E404")
        )
        second_run = self._run(2)

        _, second_problem = process_run(
            second_run, self._entries("npm ERR! code E404")
        )

        self.assertEqual(first_problem.pk, second_problem.pk)
        self.assertEqual(Problem.objects.count(), 1)
        second_problem.refresh_from_db()
        self.assertEqual(second_problem.num_occurrences, 2)
        self.assertEqual(second_run.problem_id, first_problem.pk)

    @patch("pipeline.grouping.embed_text")
    def test_different_signature_creates_problem(self, embed_text):
        embed_text.side_effect = self._embed
        first_run = self._run(1)
        _, first_problem = process_run(
            first_run, self._entries("npm ERR! code E404")
        )
        second_run = self._run(2)

        _, second_problem = process_run(
            second_run,
            self._entries("SyntaxError: Unexpected token ';'"),
        )

        self.assertNotEqual(first_problem.pk, second_problem.pk)
        self.assertEqual(Problem.objects.count(), 2)
        self.assertEqual(second_run.problem_id, second_problem.pk)

    @patch("pipeline.grouping.embed_text")
    def test_unparsed_run_detaches_problem(self, embed_text):
        embed_text.side_effect = self._embed
        run = self._run(1)
        _, problem = process_run(
            run, self._entries("npm ERR! code E404")
        )
        run.refresh_from_db()

        parsed, detached = process_run(
            run, self._entries("All checks passed")
        )

        self.assertFalse(parsed.is_parsed)
        self.assertIsNone(detached)
        run.refresh_from_db()
        self.assertIsNone(run.problem_id)
        self.assertFalse(Problem.objects.filter(pk=problem.pk).exists())
