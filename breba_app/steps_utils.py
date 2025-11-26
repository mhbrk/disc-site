import contextlib
from typing import Awaitable, Callable

import chainlit as cl

# Mapping of status messages to the step entry stored in the Chainlit session.
STATUS_STEP_KEYS: dict[str, str] = {
    "Builder is working on the specification...": "builder_step",
    "Generator is processing your request...": "generator_step",
    "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec": "generator_inner_step",
}


def clear_status_log(step_key: str) -> None:
    logs = cl.user_session.get("_status_logs") or {}
    if step_key in logs:
        logs = dict(logs)
        logs.pop(step_key, None)
        cl.user_session.set("_status_logs", logs)


def register_step(step_key: str, step: cl.Step) -> None:
    clear_status_log(step_key)
    cl.user_session.set(step_key, step)


def clear_step(step_key: str) -> None:
    cl.user_session.set(step_key, None)
    clear_status_log(step_key)


async def _append_status(step_key: str, message: str) -> bool:
    step = cl.user_session.get(step_key)
    if not step:
        return False

    logs = cl.user_session.get("_status_logs") or {}
    existing = list(logs.get(step_key, []))

    # Skip duplicating the step title inside the output stream.
    if not existing and message == step.name:
        return True
    if existing and existing[-1] == message:
        return True

    existing.append(message)
    logs = dict(logs)
    logs[step_key] = existing
    cl.user_session.set("_status_logs", logs)

    step.output = "\n".join(existing)
    update = getattr(step, "update", None)
    if callable(update):
        await update()
    return True


async def handle_status_message(message: str) -> bool:
    step_key = STATUS_STEP_KEYS.get(message)
    if not step_key:
        return False
    return await _append_status(step_key, message)


def make_stepped_generator_callback(
    step_title: str,
    downstream_cb: Callable[[str], Awaitable[None]],
    *,
    step_key: str = "generator_inner_step",
):
    """
    Create a callback that opens a nested Chainlit step for generator streaming.
    """

    class _Inner:
        def __init__(self):
            self.ctx: cl.Step | None = None
            self.opened = False

        async def _ensure_open(self):
            if self.opened:
                return
            clear_status_log(step_key)
            self.ctx = cl.Step(name=step_title)
            await self.ctx.__aenter__()
            self.opened = True
            register_step(step_key, self.ctx)

        async def __call__(self, chunk: str):
            if chunk == "__start__":
                await self._ensure_open()
                return
            if chunk == "__completed__":
                if self.opened and self.ctx:
                    with contextlib.suppress(Exception):
                        await self.ctx.__aexit__(None, None, None)
                clear_step(step_key)
                self.ctx = None
                self.opened = False
                await downstream_cb(chunk)
                return
            await self._ensure_open()
            await downstream_cb(chunk)

    return _Inner()
