import asyncio
import pytest

from palabra_ai.base.task import Task, TaskEvent


class TestTaskEvent:
    def test_set_owner(self):
        event = TaskEvent()
        event.set_owner("test_owner")
        assert event._owner == "test_owner"

    def test_pos_operator(self):
        event = TaskEvent()
        event.set_owner("test")
        +event
        assert event.is_set()

    def test_neg_operator(self):
        event = TaskEvent()
        event.set_owner("test")
        +event
        -event
        assert not event.is_set()

    def test_bool_operator(self):
        event = TaskEvent()
        assert not event
        event.set()
        assert event

    @pytest.mark.asyncio
    async def test_await_immediate(self):
        event = TaskEvent()
        event.set()
        # Should return immediately when already set
        await event

    def test_repr(self):
        event = TaskEvent()
        assert repr(event) == "TaskEvent(False)"
        event.set()
        assert repr(event) == "TaskEvent(True)"


class TestTask:
    class ConcreteTask(Task):
        async def run(self):
            +self.ready
            while not self.stopper:
                await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_task_lifecycle(self):
        task = self.ConcreteTask()
        stopper = TaskEvent()

        async with asyncio.TaskGroup() as tg:
            task(tg, stopper)
            await task.ready
            assert task._task is not None
            assert not task._task.done()

            +stopper
            await asyncio.sleep(0.02)

        assert task._task.done()

    def test_name_property(self):
        task = self.ConcreteTask()
        assert task.name == "ConcreteTask"

        task.name = "CustomName"
        assert task.name == "CustomName"

    def test_task_property_error(self):
        task = self.ConcreteTask()
        with pytest.raises(RuntimeError, match="task not set"):
            _ = task.task
