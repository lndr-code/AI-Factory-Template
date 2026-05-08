import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import run_graph


class RunGraphRegressionTests(unittest.TestCase):
    def test_task_lifecycle_status_preserves_terminal_markers(self) -> None:
        self.assertEqual(run_graph.task_lifecycle_status("tasks/01.done.md"), "done")
        self.assertEqual(run_graph.task_lifecycle_status("tasks/01.failed.md"), "failed")
        self.assertEqual(run_graph.task_lifecycle_status("tasks/01.blocked.md"), "blocked")
        self.assertIsNone(run_graph.task_lifecycle_status("tasks/01_open.md"))

    def test_find_open_tasks_uses_in_repo_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            tasks.mkdir()
            (tasks / "01_open.md").write_text("open\n", encoding="utf-8")
            (tasks / "02.done.md").write_text("done\n", encoding="utf-8")
            with patch.object(run_graph, "PROJECT_ROOT", str(root)):
                self.assertEqual(run_graph.find_open_tasks(), ["tasks/01_open.md"])

    def test_check_and_prompt_questions_empty_file_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            questions = root / "questions"
            questions.mkdir()
            (questions / "open_questions.md").write_text("# Open Questions\n", encoding="utf-8")
            with patch.object(run_graph, "PROJECT_ROOT", str(root)):
                self.assertFalse(run_graph.check_and_prompt_questions())

    def test_main_task_path_does_not_call_external_preflight(self) -> None:
        with patch.object(sys, "argv", ["run_graph.py", "--task", "tasks/01.md"]), patch.object(
            run_graph,
            "run_task",
            return_value={"task_status": "done"},
        ) as run_task, patch.object(
            run_graph,
            "run_external_preflight",
        ) as external_preflight, patch.object(
            run_graph,
            "check_and_prompt_questions",
            return_value=False,
        ):
            run_graph.main()

        run_task.assert_called_once_with("tasks/01.md")
        external_preflight.assert_not_called()

    def test_main_without_tasks_reaches_architect_flow(self) -> None:
        calls = []

        class FakeApp:
            def invoke(self, payload):
                calls.append(payload)
                return {"task_status": "done", "final_report": "planned"}

        fake_graph = types.SimpleNamespace(app=FakeApp())
        with patch.object(sys, "argv", ["run_graph.py"]), patch.object(
            run_graph,
            "find_open_tasks",
            side_effect=[[], []],
        ), patch.object(
            run_graph,
            "check_and_prompt_questions",
            return_value=False,
        ), patch.dict(
            sys.modules,
            {"orchestrator.graph": fake_graph},
        ), patch.object(
            run_graph,
            "run_external_preflight",
        ) as external_preflight:
            with redirect_stdout(StringIO()):
                run_graph.main()

        self.assertEqual(calls, [{"current_task_file": ""}])
        external_preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
