import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from palabra_ai.base.task import Task, TaskEvent


# Concrete implementation for testing
class ConcreteTask(Task):
    async def boot(self):
        pass

    async def do(self):
        pass

    async def exit(self):
        pass


class TestTaskCoverage:
    def test_task_event_coverage(self):
        """Test additional TaskEvent coverage"""
        # Test bool operator
        event = TaskEvent()
        assert not event  # False when not set
        event.set()
        assert event  # True when set

    @pytest.mark.asyncio
    async def test_run_cancelled(self):
        """Test run() when cancelled"""
        task = ConcreteTask()
        task.sub_tg = MagicMock()
        task.sub_tg.__aenter__ = AsyncMock()
        task.sub_tg.__aexit__ = AsyncMock()
        task._exit = AsyncMock(return_value=None)

        # Override do to raise CancelledError
        async def cancelled_do():
            raise asyncio.CancelledError()
        task.do = cancelled_do

        # Task re-raises CancelledError
        with pytest.raises(asyncio.CancelledError):
            await task.run()
        # Check that cancelled state was added
        assert "🚫" in task._state

    @pytest.mark.asyncio
    async def test_run_exception(self):
        """Test run() with exception"""
        task = ConcreteTask()
        task.sub_tg = MagicMock()
        task.sub_tg.__aenter__ = AsyncMock()
        task.sub_tg.__aexit__ = AsyncMock()
        task._exit = AsyncMock(return_value=None)

        # Override do to raise exception
        async def error_do():
            raise ValueError("Test error")
        task.do = error_do

        # Task re-raises exceptions
        with pytest.raises(ValueError):
            await task.run()
        # Check that error state was added
        assert "💥" in task._state

    def test_str_deep_debug(self):
        """Test string representation with DEEP_DEBUG"""
        task = ConcreteTask()
        task._state = ["🚀"]

        # Mock DEEP_DEBUG in the right place
        with patch('palabra_ai.base.task.DEEP_DEBUG', True):
            str_repr = str(task)
            # In DEEP_DEBUG mode, format is different
            assert "ready=" in str_repr
            assert "stopper=" in str_repr
            assert "eof=" in str_repr
            assert "states=" in str_repr

    @pytest.mark.asyncio
    async def test_cancel_all_subtasks(self):
        """Test cancel_all_subtasks method"""
        task = ConcreteTask()
        task._name = "TestTask"
        task._task = MagicMock()  # Set the task's own task

        # Create mock subtasks with all required attributes
        subtask1 = MagicMock()
        # Make hasattr work properly
        subtask1.get_name = MagicMock(return_value="[T]TestTask.sub1")
        subtask1.done.return_value = False
        subtask1.cancel = MagicMock()

        subtask2 = MagicMock()
        subtask2.get_name = MagicMock(return_value="[T]TestTask.sub2")
        subtask2.done.return_value = True  # Already done
        subtask2.cancel = MagicMock()

        # Mock asyncio.all_tasks
        with patch('asyncio.all_tasks', return_value=[subtask1, subtask2]):
            # Mock asyncio.wait
            with patch('asyncio.wait', new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = (set(), set())

                await task.cancel_all_subtasks()

                # Verify that only the non-done subtask was cancelled
                subtask1.cancel.assert_called_once()
                subtask2.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_exit_timeout(self):
        """Test _exit when exit() times out"""
        task = ConcreteTask()

        # Make exit() hang forever
        async def hanging_exit():
            await asyncio.sleep(100)
        task.exit = hanging_exit
        task.cancel_all_subtasks = AsyncMock()

        with patch('palabra_ai.constant.SHUTDOWN_TIMEOUT', 0.1):
            # Should timeout and call cancel_all_subtasks
            await task._exit()
            task.cancel_all_subtasks.assert_called_once()

    def test_task_property_error(self):
        """Test task property when not set"""
        task = ConcreteTask()
        with pytest.raises(RuntimeError, match="task not set"):
            _ = task.task

    def test_name_setter(self):
        """Test name setter"""
        task = ConcreteTask()
        task.name = "CustomName"
        assert task._name == "CustomName"
        assert task.name == "[T]CustomName"

    @pytest.mark.asyncio
    async def test_task_event_await(self):
        """Test TaskEvent await functionality"""
        event = TaskEvent()

        # When already set, should return immediately
        event.set()
        await event  # Should not block

        # Test repr
        assert "TaskEvent(True)" in repr(event)

    def test_task_event_pos_neg(self):
        """Test TaskEvent pos/neg operators"""
        event = TaskEvent()
        event.set_owner("test.event")

        # Test __pos__ (set)
        +event
        assert event.is_set()

        # Test __neg__ (clear)
        -event
        assert not event.is_set()

    def test_str_normal_mode(self):
        """Test string representation in normal mode"""
        task = ConcreteTask()
        task._state = ["🚀", "🌀"]

        with patch('palabra_ai.base.task.DEEP_DEBUG', False):
            str_repr = str(task)
            # Should have emoji format
            assert "🎬" in str_repr
            assert "🪦" in str_repr
            assert "🏁" in str_repr
            assert "🚀🌀" in str_repr
