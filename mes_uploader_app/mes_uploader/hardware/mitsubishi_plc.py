# -*- coding: utf-8 -*-
"""
Đọc / ghi thanh ghi PLC Mitsubishi FX5U (dòng iQ-F) qua Ethernet (LAN).

PLC FX5U-80M có cổng LAN tích hợp, hỗ trợ giao thức MC Protocol / SLMP
(khung 3E - binary). Module này dùng socket TCP thuần, KHÔNG cần cài thư
viện ngoài, nên chạy được ngay với Python tiêu chuẩn.

--- Cấu hình phía PLC (GX Works3) ---
1. Parameter > FX5UCPU > Module Parameter > Ethernet Port
2. Mục "Own Node Settings": đặt IP cho PLC, ví dụ 192.168.1.250
3. Mục "External Device Configuration": thêm thiết bị
   "SLMP Connection Module", đặt Port (ví dụ 5000), Protocol = TCP.
4. Write parameter xuống PLC và reset nguồn.

--- Loại thanh ghi (device) hỗ trợ ---
   D  : Data register  (word)   - hay dùng nhất
   W  : Link register  (word)
   R  : File register   (word)
   M  : Internal relay  (bit)
   X  : Input           (bit)
   Y  : Output          (bit)
"""

import socket
import struct


# Mã device cho khung 3E binary (mã loại thiết bị, đơn vị bit/word)
#   code      : 1 byte mã thiết bị
#   is_bit    : True nếu là thiết bị bit, False nếu là word
DEVICE_CODES = {
    'D': (0xA8, False),   # Data register
    'W': (0xB4, False),   # Link register
    'R': (0xAF, False),   # File register
    'M': (0x90, True),    # Internal relay
    'X': (0x9C, True),    # Input
    'Y': (0x9D, True),    # Output
    'L': (0x92, True),    # Latch relay
    'B': (0xA0, True),    # Link relay
}

# Tiền tố các thiết bị WORD (đọc/ghi theo GIÁ TRỊ, vd D100); còn lại là BIT.
WORD_DEVICE_PREFIXES = {name for name, (_c, is_bit) in DEVICE_CODES.items()
                        if not is_bit}


def is_word_device(device):
    """True nếu 'device' là thanh ghi WORD (D/W/R...), False nếu BIT (M/X/Y...).

    Worker dùng hàm này để TỰ chọn đọc/ghi theo word hay bit cho trigger/done.
    Tiền tố lạ -> coi là BIT (giữ hành vi cũ, an toàn).
    """
    d = (device or "").strip().upper()
    i = 0
    while i < len(d) and not d[i].isdigit():
        i += 1
    return d[:i] in WORD_DEVICE_PREFIXES


class MitsubishiPLC:
    """Kết nối tới PLC Mitsubishi FX5U qua MC Protocol 3E (binary, TCP)."""

    def __init__(self, ip, port=5000, timeout=3.0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock = None

    # ------------------------------------------------------------------ #
    #  Kết nối                                                            #
    # ------------------------------------------------------------------ #
    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.ip, self.port))
        return self

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ------------------------------------------------------------------ #
    #  Tách tên thanh ghi "D100" -> ('D', 100)                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_device(device):
        device = device.strip().upper()
        # tách phần chữ (loại) và phần số (địa chỉ)
        i = 0
        while i < len(device) and not device[i].isdigit():
            i += 1
        dtype = device[:i]
        addr = int(device[i:])
        if dtype not in DEVICE_CODES:
            raise ValueError("Loai thanh ghi khong ho tro: %s" % dtype)
        return dtype, addr

    # ------------------------------------------------------------------ #
    #  Đóng khung 3E và gửi / nhận                                        #
    # ------------------------------------------------------------------ #
    def _recv_exact(self, n):
        """Đọc ĐỦ n byte từ socket (TCP có thể trả về từng phần / phân mảnh)."""
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise IOError("PLC dong ket noi khi dang doc")
            buf += chunk
        return bytes(buf)

    def _send_recv(self, request_data):
        """Bọc phần command (request_data) vào khung 3E rồi gửi, trả về data."""
        # --- Subheader + network info (cố định cho 3E binary) ---
        subheader = b'\x50\x00'          # 5000: 3E frame
        network_no = b'\x00'             # mạng cục bộ
        pc_no = b'\xFF'                  # CPU cục bộ
        dst_module_io = b'\xFF\x03'      # 03FF: CPU đích
        dst_module_sta = b'\x00'
        cpu_timer = b'\x10\x00'          # thời gian chờ CPU (16 * 250ms)

        # độ dài = cpu_timer (2) + request_data
        data_len = struct.pack('<H', len(cpu_timer) + len(request_data))

        frame = (subheader + network_no + pc_no + dst_module_io +
                 dst_module_sta + data_len + cpu_timer + request_data)

        self.sock.sendall(frame)

        # Phản hồi 3E: 9 byte đầu (tới hết trường 'độ dài'), rồi đọc ĐÚNG
        # 'độ dài' byte tiếp theo (gồm end_code 2 byte + dữ liệu). Đọc đủ để
        # tránh nhận thiếu khi PLC trả phản hồi bị phân mảnh (lỗi 'unpack
        # requires a buffer of 2 bytes').
        head = self._recv_exact(9)
        resp_len = struct.unpack('<H', head[7:9])[0]
        body = self._recv_exact(resp_len)

        end_code = struct.unpack('<H', body[0:2])[0]
        if end_code != 0:
            raise IOError("PLC tra ve loi, end code = 0x%04X" % end_code)

        return body[2:]   # phần dữ liệu sau end_code

    @staticmethod
    def _device_bytes(dtype, addr):
        """3 byte địa chỉ (little endian) + 1 byte mã device."""
        code, _ = DEVICE_CODES[dtype]
        return struct.pack('<I', addr)[:3] + struct.pack('B', code)

    # ------------------------------------------------------------------ #
    #  ĐỌC thanh ghi word (D, W, R...)                                    #
    # ------------------------------------------------------------------ #
    def read_words(self, device, count=1):
        """Đọc 'count' word liên tiếp từ 'device' (vd 'D100'). Trả list int."""
        dtype, addr = self._parse_device(device)
        command = b'\x01\x04'          # batch read
        subcommand = b'\x00\x00'       # đơn vị word
        req = (command + subcommand +
               self._device_bytes(dtype, addr) +
               struct.pack('<H', count))
        data = self._send_recv(req)
        return [struct.unpack('<H', data[i:i + 2])[0]
                for i in range(0, count * 2, 2)]

    def read_word(self, device):
        """Đọc 1 word, trả về 1 số nguyên (0..65535)."""
        return self.read_words(device, 1)[0]

    # ------------------------------------------------------------------ #
    #  GHI thanh ghi word                                                 #
    # ------------------------------------------------------------------ #
    def write_words(self, device, values):
        """Ghi danh sách word vào 'device' liên tiếp. values: int hoặc list."""
        if isinstance(values, int):
            values = [values]
        dtype, addr = self._parse_device(device)
        command = b'\x01\x14'          # batch write
        subcommand = b'\x00\x00'       # đơn vị word
        payload = b''.join(struct.pack('<H', v & 0xFFFF) for v in values)
        req = (command + subcommand +
               self._device_bytes(dtype, addr) +
               struct.pack('<H', len(values)) + payload)
        self._send_recv(req)
        return True

    def write_word(self, device, value):
        """Ghi 1 word."""
        return self.write_words(device, [value])

    # ------------------------------------------------------------------ #
    #  ĐỌC / GHI bit (M, X, Y...)                                         #
    # ------------------------------------------------------------------ #
    def read_bits(self, device, count=1):
        """Đọc 'count' bit liên tiếp (vd 'M0'). Trả list 0/1."""
        dtype, addr = self._parse_device(device)
        command = b'\x01\x04'          # batch read
        subcommand = b'\x01\x00'       # đơn vị bit
        req = (command + subcommand +
               self._device_bytes(dtype, addr) +
               struct.pack('<H', count))
        data = self._send_recv(req)
        # mỗi byte chứa 2 bit (nibble cao / thấp)
        bits = []
        for b in data:
            bits.append((b >> 4) & 1)
            bits.append(b & 1)
        return bits[:count]

    def read_bit(self, device):
        return self.read_bits(device, 1)[0]

    def write_bits(self, device, values):
        """Ghi danh sách bit (0/1) vào 'device' liên tiếp."""
        if isinstance(values, int):
            values = [values]
        dtype, addr = self._parse_device(device)
        command = b'\x01\x14'          # batch write
        subcommand = b'\x01\x00'       # đơn vị bit
        # đóng gói 2 bit / byte
        payload = bytearray()
        for i in range(0, len(values), 2):
            hi = 0x10 if values[i] else 0x00
            lo = 0x01 if (i + 1 < len(values) and values[i + 1]) else 0x00
            payload.append(hi | lo)
        req = (command + subcommand +
               self._device_bytes(dtype, addr) +
               struct.pack('<H', len(values)) + bytes(payload))
        self._send_recv(req)
        return True

    def write_bit(self, device, value):
        return self.write_bits(device, [1 if value else 0])

    # ------------------------------------------------------------------ #
    #  SỐ FLOAT (REAL - 32 bit) và SỐ NGUYÊN 32 bit (DWORD)              #
    #  -> chiếm 2 thanh ghi D liên tiếp (vd D100 = D100 + D101)          #
    #  Thứ tự word của Mitsubishi: word THẤP nằm trước (little endian)   #
    # ------------------------------------------------------------------ #
    def read_float(self, device, count=1):
        """Đọc số thực 32-bit. count = số float cần đọc (mỗi float = 2 word)."""
        words = self.read_words(device, count * 2)
        result = []
        for i in range(0, len(words), 2):
            raw = struct.pack('<HH', words[i], words[i + 1])  # word thấp trước
            result.append(struct.unpack('<f', raw)[0])
        return result[0] if count == 1 else result

    def write_float(self, device, values):
        """Ghi số thực 32-bit. values: float hoặc list float."""
        if isinstance(values, (int, float)):
            values = [values]
        words = []
        for v in values:
            lo, hi = struct.unpack('<HH', struct.pack('<f', float(v)))
            words += [lo, hi]
        return self.write_words(device, words)

    def read_dword(self, device, count=1, signed=True):
        """Đọc số nguyên 32-bit (DWORD/DINT). Mỗi số = 2 word."""
        words = self.read_words(device, count * 2)
        fmt = '<i' if signed else '<I'
        result = []
        for i in range(0, len(words), 2):
            raw = struct.pack('<HH', words[i], words[i + 1])
            result.append(struct.unpack(fmt, raw)[0])
        return result[0] if count == 1 else result

    def write_dword(self, device, values, signed=True):
        """Ghi số nguyên 32-bit (DWORD/DINT). values: int hoặc list int."""
        if isinstance(values, int):
            values = [values]
        fmt = '<i' if signed else '<I'
        words = []
        for v in values:
            lo, hi = struct.unpack('<HH', struct.pack(fmt, int(v)))
            words += [lo, hi]
        return self.write_words(device, words)


# ---------------------------------------------------------------------- #
#  Hàm tiện dụng                                                          #
# ---------------------------------------------------------------------- #
def read_data_mitsubishi(ip, port, device, count=1):
    try:
        with MitsubishiPLC(ip, port) as plc:
            vals = plc.read_words(device, count)
            return vals[0] if count == 1 else vals
    except Exception as ex:
        print("Loi doc PLC:", ex)
        return None


def write_data_mitsubishi(ip, port, device, value):
    try:
        with MitsubishiPLC(ip, port) as plc:
            plc.write_word(device, value)
            return True
    except Exception as ex:
        print("Loi ghi PLC:", ex)
        return False
