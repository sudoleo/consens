"""The history of a public page, kept in the process for all its versions.

Crawlers ask for every ``?version=`` of a Topic or Watch page one by one, and
each view read the whole history again: up to 100 Firestore documents, while
the free tier is 50,000 reads a day. A page's history changes only together
with a few fields of the document the route reads anyway (its *mark*: the
Topic, the Watch and its share). So the history is kept as long as the mark
is the same. A run written by another process (a local server writes to the
same database) changes the mark the next view reads, never only an
in-process flag.
"""

import threading
import zlib
from collections import OrderedDict

_MISSING = object()


class HistoryCache:
    """One history per page, valid for exactly one mark, least recently used
    pages dropped first.

    The cached value is shared by every view of the page: callers treat it
    as read-only.
    """

    def __init__(self, max_pages: int, *, stripes: int = 16):
        self._max_pages = max_pages
        self._entries: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        # Views of one page that miss together wait for the first read
        # instead of each reading the whole history (a crawler's burst right
        # after a deploy). Striped, so the locks never grow with the pages.
        self._loading = [threading.Lock() for _ in range(stripes)]

    def _get(self, page_id, mark):
        with self._lock:
            entry = self._entries.get(page_id)
            if entry is None or entry[0] != mark:
                return _MISSING
            self._entries.move_to_end(page_id)
            return entry[1]

    def get_or_load(self, page_id, mark, load):
        """The page's history for ``mark``; ``load()`` reads it on a miss.

        ``load`` runs only after the caller read ``mark``, so what it returns
        is at least as new as the mark it is stored under. A failed read
        stores nothing.
        """
        value = self._get(page_id, mark)
        if value is not _MISSING:
            return value
        stripe = zlib.crc32(str(page_id).encode("utf-8")) % len(self._loading)
        with self._loading[stripe]:
            value = self._get(page_id, mark)
            if value is not _MISSING:
                return value
            value = load()
            with self._lock:
                self._entries[page_id] = (mark, value)
                self._entries.move_to_end(page_id)
                while len(self._entries) > self._max_pages:
                    self._entries.popitem(last=False)
            return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
