"""FSM state groups for multi-step bot conversations."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SetAlertStates(StatesGroup):
    waiting_for_threshold = State()
    waiting_for_direction = State()
