import asyncio
import sys

import pytest


@pytest.fixture()
def event_loop():
    """Fixture of @pytest.mark.asyncio()."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
