"""Fixtures to ensure proper async cleanup in tests."""

import pytest
import asyncio
import gc
import warnings


@pytest.fixture(autouse=True)
def ensure_async_cleanup():
    """Ensure any pending async tasks are cleaned up between tests."""
    # Run before test
    loop = asyncio.get_event_loop()
    pending = asyncio.all_tasks(loop) if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks(loop)
    for task in pending:
        if not task.done():
            task.cancel()
    
    yield
    
    # Run after test - clean up any pending coroutines
    loop = asyncio.get_event_loop()
    
    # Cancel any pending tasks
    pending = asyncio.all_tasks(loop) if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks(loop)
    for task in pending:
        if not task.done():
            task.cancel()
    
    # Run the event loop briefly to process cancellations
    try:
        loop.run_until_complete(asyncio.sleep(0))
    except:
        pass
    
    # Force garbage collection with warning suppression
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*coroutine.*was never awaited")
        gc.collect()


@pytest.fixture
def clean_async_state():
    """Fixture to use when you need to ensure clean async state."""
    # Get current event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Clean any pending tasks
    pending = asyncio.all_tasks(loop) if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks(loop)
    for task in pending:
        if not task.done():
            task.cancel()
    
    yield loop
    
    # Cleanup
    pending = asyncio.all_tasks(loop) if hasattr(asyncio, 'all_tasks') else asyncio.Task.all_tasks(loop)
    for task in pending:
        if not task.done():
            task.cancel()