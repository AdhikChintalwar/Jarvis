from __future__ import annotations

from voice.sensevoice_asr import (
    listen_sensevoice,
)


def listen_streaming() -> str:
    """
    Public listener interface used by Baby sessions.

    The implementation can be swapped later without
    changing session_manager.py.
    """
    return listen_sensevoice()