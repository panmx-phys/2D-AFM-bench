"""Small process-local LRU caches; persisted source data remains authoritative."""
from collections import OrderedDict


class MemoryCache:
    def __init__(self, max_bytes, max_entries):
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.size = 0
        self._items = OrderedDict()

    def get(self, key):
        item = self._items.get(key)
        if item is None:
            return None
        self._items.move_to_end(key)
        return item[0]

    def put(self, key, value, size):
        # Include the key and a fixed allowance for entry/container overhead.
        size += len(repr(key).encode('utf-8')) + 256
        old = self._items.pop(key, None)
        if old is not None:
            self.size -= old[1]
        if size > self.max_bytes or self.max_entries < 1:
            return
        while self._items and (self.size + size > self.max_bytes or len(self._items) >= self.max_entries):
            _, (_, removed) = self._items.popitem(last=False)
            self.size -= removed
        self._items[key] = (value, size)
        self.size += size

    def clear(self):
        self._items.clear()
        self.size = 0
