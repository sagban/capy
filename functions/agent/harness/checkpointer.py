"""LangGraph checkpointer: MemorySaver in tests, Firestore in production."""

from __future__ import annotations

import os
from typing import Any

_CHECKPOINTER = None


def _use_memory() -> bool:
    return os.environ.get("CAPY_MOCK_AGENT") == "1" or os.environ.get("CAPY_CHECKPOINT") == "memory"


def get_checkpointer() -> Any:
    global _CHECKPOINTER
    if _CHECKPOINTER is not None:
        return _CHECKPOINTER
    if _use_memory():
        from langgraph.checkpoint.memory import MemorySaver

        _CHECKPOINTER = MemorySaver()
        return _CHECKPOINTER
    try:
        from google.cloud import firestore
        from langgraph_checkpoint_firestore import FirestoreSaver

        project = (
            os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCLOUD_PROJECT")
            or os.environ.get("GCP_PROJECT")
            or "capy-dogfood"
        )
        database_id = os.environ.get("FIRESTORE_DATABASE_ID", "capy").strip() or "capy"
        collection = "agentGraphCheckpoints"
        # from_conn_info is a @contextmanager — do not pass it to compile().
        # Library hardcodes Client(project=…) → (default); rebind to named DB `capy`.
        saver = FirestoreSaver(
            project_id=project,
            checkpoints_collection=collection,
        )
        saver.client = firestore.Client(project=project, database=database_id)
        saver.checkpoints_collection = saver.client.collection(collection)
        _CHECKPOINTER = saver
        return _CHECKPOINTER
    except Exception:  # noqa: BLE001
        from langgraph.checkpoint.memory import MemorySaver

        _CHECKPOINTER = MemorySaver()
        return _CHECKPOINTER


def reset_checkpointer() -> None:
    global _CHECKPOINTER
    _CHECKPOINTER = None
