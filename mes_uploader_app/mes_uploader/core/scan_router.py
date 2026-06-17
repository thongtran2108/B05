# -*- coding: utf-8 -*-
"""Điều phối 1 MÁY QUÉT DÙNG CHUNG cho 2 bên (Trái / Phải) — luân phiên theo lượt.

Quy tắc (theo yêu cầu):
  - Bắt đầu: tới lượt bên TRÁI.
  - Quét 1 mã -> đưa cho bên ĐANG TỚI LƯỢT. App check SN (GET):
      * HỢP LỆ (OK) -> CHUYỂN lượt sang bên kia (bên vừa quét tự đo bằng PLC).
      * KHÔNG hợp lệ (NG) -> GIỮ lượt, quét lại bên đó.
  - Bên đang tới lượt được làm sáng trên giao diện để biết quét bên nào.

Lớp này CHỈ giữ trạng thái lượt (thuần Python, không phụ thuộc Qt/phần cứng) để
dễ kiểm thử; phần mở cổng COM + làm sáng UI do lớp giao diện gọi.
"""

OTHER = {"left": "right", "right": "left"}


class ScanRouter:
    def __init__(self, start="left"):
        self.turn = start if start in OTHER else "left"

    def route(self):
        """Bên sẽ NHẬN mã quét tiếp theo (= bên đang tới lượt)."""
        return self.turn

    def on_result(self, side, ok):
        """Cập nhật lượt theo kết quả check SN của bên VỪA QUÉT.

        Chỉ xét sự kiện của ĐÚNG bên đang tới lượt (bỏ qua sự kiện lạ). OK ->
        chuyển sang bên kia; NG -> giữ nguyên. Trả về bên tới lượt sau cập nhật.
        """
        if side == self.turn and ok:
            self.turn = OTHER[self.turn]
        return self.turn
