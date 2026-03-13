"""AnkiConnect API client.

Communicates with the AnkiConnect plugin (https://foosoft.net/projects/anki-connect/)
running inside the Anki desktop application on localhost:8765.

Requires:
  - Anki desktop running
  - AnkiConnect plugin installed (code: 2055492159)
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Defaults — importable from config, but overridable via constructor
_DEFAULT_URL = "http://localhost:8765"
_DEFAULT_VERSION = 6


class AnkiConnectError(Exception):
    """Raised when AnkiConnect returns an error."""


class AnkiConnect:
    """Client for the AnkiConnect REST API."""

    def __init__(self, url: str | None = None, version: int | None = None):
        self.url = url or _DEFAULT_URL
        self.version = version or _DEFAULT_VERSION

    # ─── Low-level API ────────────────────────────────────────────

    def _request(self, action: str, **params) -> Any:
        """Send a request to AnkiConnect and return the result."""
        payload: dict[str, Any] = {"action": action, "version": self.version}
        if params:
            payload["params"] = params

        request_json = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, request_json)
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req) as response:
                body = json.loads(response.read())
        except urllib.error.URLError as exc:
            raise AnkiConnectError(
                f"Cannot reach AnkiConnect at {self.url}. "
                "Is Anki running with the AnkiConnect plugin installed?"
            ) from exc

        if body.get("error"):
            raise AnkiConnectError(body["error"])
        return body.get("result")

    # ─── Connection ───────────────────────────────────────────────

    def ping(self) -> bool:
        """Check that AnkiConnect is reachable."""
        try:
            result = self._request("version")
            logger.info("AnkiConnect version %s is running", result)
            return True
        except AnkiConnectError:
            return False

    # ─── Decks ────────────────────────────────────────────────────

    def deck_names(self) -> list[str]:
        """Return all deck names."""
        return self._request("deckNames")

    def create_deck(self, name: str) -> int:
        """Create a deck (no-op if it already exists). Returns deck ID."""
        return self._request("createDeck", deck=name)

    # ─── Models (Note Types) ─────────────────────────────────────

    def model_names(self) -> list[str]:
        """Return all model (note type) names."""
        return self._request("modelNames")

    def create_model(
        self,
        name: str,
        fields: list[str],
        card_templates: list[dict],
        css: str = "",
    ) -> dict:
        """Create a note type if it doesn't already exist."""
        existing = self.model_names()
        if name in existing:
            logger.info("Model '%s' already exists, skipping creation", name)
            return {}

        return self._request(
            "createModel",
            modelName=name,
            inOrderFields=fields,
            cardTemplates=card_templates,
            css=css,
        )

    # ─── Notes ────────────────────────────────────────────────────

    def find_notes(self, query: str) -> list[int]:
        """Find note IDs matching a query (Anki search syntax)."""
        return self._request("findNotes", query=query)

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        """Get full info for a list of note IDs."""
        return self._request("notesInfo", notes=note_ids)

    def add_note(
        self,
        deck: str,
        model: str,
        fields: dict[str, str],
        tags: Optional[list[str]] = None,
        allow_duplicate: bool = False,
    ) -> Optional[int]:
        """Add a single note. Returns the note ID, or None if duplicate."""
        note = {
            "deckName": deck,
            "modelName": model,
            "fields": fields,
            "tags": tags or [],
            "options": {"allowDuplicate": allow_duplicate},
        }
        try:
            return self._request("addNote", note=note)
        except AnkiConnectError as exc:
            if "duplicate" in str(exc).lower():
                logger.debug("Skipping duplicate note: %s", fields)
                return None
            raise

    def add_notes(
        self,
        deck: str,
        model: str,
        notes_fields: list[dict[str, str]],
        tags: Optional[list[str]] = None,
        allow_duplicate: bool = False,
    ) -> list[Optional[int]]:
        """Add multiple notes at once. Returns list of note IDs."""
        notes = [
            {
                "deckName": deck,
                "modelName": model,
                "fields": fields,
                "tags": tags or [],
                "options": {"allowDuplicate": allow_duplicate},
            }
            for fields in notes_fields
        ]
        return self._request("addNotes", notes=notes)

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> None:
        """Update fields of an existing note."""
        self._request("updateNoteFields", note={"id": note_id, "fields": fields})

    def add_tags(self, note_ids: list[int], tags: str) -> None:
        """Add space-separated tags to notes."""
        self._request("addTags", notes=note_ids, tags=tags)

    # ─── Convenience ──────────────────────────────────────────────

    def get_deck_notes(self, deck: str) -> list[dict]:
        """Get all notes from a deck with full field data."""
        note_ids = self.find_notes(f'"deck:{deck}"')
        if not note_ids:
            return []
        return self.notes_info(note_ids)

    def ensure_deck(self, name: str) -> int:
        """Create deck if it doesn't exist, return deck ID."""
        return self.create_deck(name)

    def set_due_position(self, note_id: int, position: int) -> None:
        """Set the due position for all cards belonging to a note.

        This controls the order Anki uses when presenting new cards in
        'ordered' deck mode. Lower positions are shown first.
        """
        card_ids = self._request("findCards", query=f"nid:{note_id}")
        if card_ids:
            self._request(
                "setSpecificValueOfCard",
                card=card_ids[0],
                keys=["due"],
                newValues=[str(position)],
            )
