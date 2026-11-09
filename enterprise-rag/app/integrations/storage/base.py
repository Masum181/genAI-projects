"""Provider-neutral object storage contract."""

from typing import Protocol


class ObjectStorage(Protocol):
    """Contract for storing and retrieving opaque document objects."""

    async def upload(
        self, object_key: str, content: bytes, *, content_type: str
    ) -> None:
        """Persist object bytes under a storage key."""

    async def download(self, object_key: str) -> bytes:
        """Return the bytes for a previously stored object."""

    async def delete(self, object_key: str) -> None:
        """Delete a stored object by key."""
