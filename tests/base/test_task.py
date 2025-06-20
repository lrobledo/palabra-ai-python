import asyncio
import pytest
from palabra_ai.base.task import Task, TaskEvent
from unittest.mock import MagicMock, patch


class ConcreteTask(Task):
    """Concrete implementation for testing."""

    async def boot(self):
        await asyncio.sleep(0.01)

    async def do(self):
        await asyncio.sleep(0.01)

    async def exit(self):
        return "exit_result"


class TestTask:
    @pytest.mark.asyncio
    async def test_cancel_all_subtasks(self):
        task = ConcreteTask()

        # Mock some subtasks
        mock_task1 = MagicMock()
        mock_task1.get_name.return_value = "[T]ConcreteTask_subtask1"
        mock_task1.done.return_value = False
        mock_task1.cancel = MagicMock()

        mock_task2 = MagicMock()
        mock_task2.get_name.return_value = "[T]ConcreteTask_subtask2"
        mock_task2.done.return_value = True  # Already done

        # Mock asyncio.all_tasks
        with patch('asyncio.all_tasks', return_value={mock_task1, mock_task2}):
            with patch('asyncio.wait', return_value=(set(), {mock_task1})):
                await task.cancel_all_subtasks()

        # Only non-done task should be cancelled
        mock_task1.cancel.assert_called()
        assert mock_task1.cancel.call_count == 2  # Once normally, once force

    @pytest.mark.asyncio
    async def test_exit_timeout(self):
        class SlowExitTask(Task):
            async def boot(self):
                pass

            async def do(self):
                pass

            async def exit(self):
                await asyncio.sleep(10)  # Longer than timeout

        task = SlowExitTask()
        task.cancel_all_subtasks = MagicMock(return_value=asyncio.Future())
        task.cancel_all_subtasks.return_value.set_result(None)

        with patch('palabra_ai.constant.SHUTDOWN_TIMEOUT', 0.1):
            await task._exit()

        task.cancel_all_subtasks.assert_called_once()

    def test_name_setter(self):
        task = ConcreteTask()
        task.name = "CustomName"
        assert task.name == "[T]CustomName"

    def test_task_not_set_error(self):
        task = ConcreteTask()
        with pytest.raises(RuntimeError, match="task not set"):
            _ = task.task
