import asyncio
import traceback
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class TaskInfo:
    """Information about a hanging task"""
    name: str
    coro_name: str
    location: str
    stack_frames: List[Tuple[str, int, str, Optional[str]]]
    state: str


def is_user_code(filename: str) -> bool:
    """Check if the file is user code (not stdlib or third-party)"""
    if not filename:
        return False

    # Skip standard library and common async libraries
    skip_patterns = [
        'asyncio/', 'concurrent/', 'threading.py',
        'selectors.py', 'socket.py', 'ssl.py',
        'site-packages/', 'dist-packages/',
        '<frozen', '<built-in>', '<string>'
    ]

    return not any(pattern in filename for pattern in skip_patterns)


def get_meaningful_frames(stack: List, max_frames: int = 3) -> List[Tuple[str, int, str, Optional[str]]]:
    """Extract only meaningful frames from stack trace"""
    frames = []

    for frame in reversed(stack):
        filename = frame.f_code.co_filename
        if is_user_code(filename):
            # Get the actual code line
            lineno = frame.f_lineno
            func_name = frame.f_code.co_name

            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    code_line = lines[lineno - 1].strip() if lineno <= len(lines) else None
            except:
                code_line = None

            frames.append((
                Path(filename).name,  # Just filename, not full path
                lineno,
                func_name,
                code_line
            ))

            if len(frames) >= max_frames:
                break

    return frames


def diagnose_hanging_tasks(show_all: bool = False) -> None:
    """
    Diagnose hanging asyncio tasks from user code

    Args:
        show_all: If True, show all tasks including system ones
    """
    try:
        # Get current event loop
        loop = asyncio.get_running_loop()
        current_task = asyncio.current_task(loop)
        all_tasks = asyncio.all_tasks(loop)

        # Collect task information
        hanging_tasks = []

        for task in all_tasks:
            # Skip current task (the one running diagnostics)
            if task is current_task:
                continue

            # Get task info
            coro = task.get_coro()
            task_name = task.get_name()
            coro_name = coro.__name__ if hasattr(coro, '__name__') else str(coro)

            # Get stack
            stack = task.get_stack()
            if not stack:
                continue

            # Get the current location
            current_frame = stack[-1]
            current_file = current_frame.f_code.co_filename

            # Skip if not user code (unless show_all)
            if not show_all and not is_user_code(current_file):
                continue

            # Get meaningful frames
            frames = get_meaningful_frames(stack)
            if not frames and not show_all:
                continue

            # Current location info
            location = f"{Path(current_file).name}:{current_frame.f_lineno}"

            # Task state
            if task.done():
                state = "DONE"
                if task.cancelled():
                    state = "CANCELLED"
                elif task.exception():
                    state = f"ERROR: {task.exception()}"
            else:
                state = "RUNNING"

            hanging_tasks.append(TaskInfo(
                name=task_name,
                coro_name=coro_name,
                location=location,
                stack_frames=frames,
                state=state
            ))

        # Print diagnosis
        if not hanging_tasks:
            print("✓ No hanging user tasks found")
            return

        print(f"\n🔍 Found {len(hanging_tasks)} hanging task(s):\n")
        print("-" * 60)

        # Group by similar locations
        location_groups = defaultdict(list)
        for task_info in hanging_tasks:
            location_groups[task_info.location].append(task_info)

        # Display grouped tasks
        for location, tasks in location_groups.items():
            print(f"\n📍 {location} ({len(tasks)} task(s))")

            for i, task in enumerate(tasks):
                prefix = "  └─" if i == len(tasks) - 1 else "  ├─"
                print(f"{prefix} {task.name} [{task.coro_name}] - {task.state}")

                # Show stack trace for first task in group or if different
                if i == 0 or task.stack_frames != tasks[0].stack_frames:
                    for j, (file, line, func, code) in enumerate(task.stack_frames):
                        indent = "     " if i == len(tasks) - 1 else "  │  "
                        arrow = "→" if j == 0 else " "
                        print(f"{indent}  {arrow} {file}:{line} in {func}()")
                        if code:
                            print(f"{indent}     {code[:50]}{'...' if len(code) > 50 else ''}")

        print("\n" + "-" * 60)

    except RuntimeError:
        print("❌ No running event loop. Call from within async context.")


async def diagnose_hanging_tasks_async(show_all: bool = False) -> List[TaskInfo]:
    """
    Async version that returns task info as list

    Returns:
        List of TaskInfo objects for further processing
    """
    loop = asyncio.get_running_loop()
    current_task = asyncio.current_task(loop)
    all_tasks = asyncio.all_tasks(loop)

    hanging_tasks = []

    for task in all_tasks:
        if task is current_task:
            continue

        coro = task.get_coro()
        task_name = task.get_name()
        coro_name = coro.__name__ if hasattr(coro, '__name__') else str(coro)

        stack = task.get_stack()
        if not stack:
            continue

        current_frame = stack[-1]
        current_file = current_frame.f_code.co_filename

        if not show_all and not is_user_code(current_file):
            continue

        frames = get_meaningful_frames(stack)
        if not frames and not show_all:
            continue

        location = f"{Path(current_file).name}:{current_frame.f_lineno}"

        if task.done():
            state = "DONE"
            if task.cancelled():
                state = "CANCELLED"
            elif task.exception():
                state = f"ERROR: {task.exception()}"
        else:
            state = "RUNNING"

        hanging_tasks.append(TaskInfo(
            name=task_name,
            coro_name=coro_name,
            location=location,
            stack_frames=frames,
            state=state
        ))

    return hanging_tasks


# Example usage and test
if __name__ == "__main__":
    async def hanging_task():
        """Example of hanging task"""
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour

    async def io_waiting_task():
        """Task waiting for I/O"""
        reader, writer = await asyncio.open_connection('example.com', 80)
        data = await reader.read(1024)

    async def main():
        # Create some hanging tasks
        task1 = asyncio.create_task(hanging_task(), name="HangingTask-1")
        task2 = asyncio.create_task(hanging_task(), name="HangingTask-2")

        # Wait a bit
        await asyncio.sleep(0.1)

        # Run diagnostics
        print("Running diagnostics...")
        diagnose_hanging_tasks()

        # Cancel tasks
        task1.cancel()
        task2.cancel()

        try:
            await asyncio.gather(task1, task2)
        except asyncio.CancelledError:
            pass

    # Run example
    asyncio.run(main())


async def monitor_tasks_periodically():
    """Monitor tasks every N seconds"""
    while True:
        try:
            await asyncio.sleep(10)  # Check every 5 seconds

            print("\n⏰ Periodic check:")
            diagnose_hanging_tasks()
        except asyncio.CancelledError:
            print("🛑 Monitor task cancelled, stopping periodic checks.")
            continue

async def main():

    # Start monitoring
    monitor_task = asyncio.create_task(monitor_tasks_periodically(), name="Monitor")

