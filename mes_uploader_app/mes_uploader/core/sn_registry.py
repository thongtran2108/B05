# -*- coding: utf-8 -*-
"""Theo dõi SN đang CHẠY ở mỗi bên để CHẶN 2 bên trùng mã (2 bên phải khác mã).

Khi 1 bên nhận & đang chạy 1 SN, bên kia quét ĐÚNG mã đó sẽ bị chặn cho tới khi
bên đang chạy hoàn tất (hoặc hủy). An toàn nhiều luồng (mỗi bên 1 worker riêng).
"""

import threading


class ActiveSnRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._active = {}                 # side_key -> SN đang chạy

    def taken_by_other(self, side_key, sn):
        """SN này đang chạy ở BÊN KHÁC (không phải side_key) không?"""
        sn = (sn or "").strip()
        if not sn:
            return False
        with self._lock:
            return any(k != side_key and v == sn for k, v in self._active.items())

    def acquire(self, side_key, sn):
        """Đánh dấu side_key đang chạy SN này."""
        with self._lock:
            self._active[side_key] = (sn or "").strip()

    def release(self, side_key):
        """Bỏ đánh dấu bên này (xong / hủy / dừng)."""
        with self._lock:
            self._active.pop(side_key, None)
