"""Tests for wallmotion.frames - needs QtGui (skipped headless)."""

import pytest

QtGui = pytest.importorskip("PySide6.QtGui")

from wallmotion.frames import ensure_packed_rgb32  # noqa: E402


def _padded_rgb32(w=8, h=4, stride=40):
    buf = bytearray(stride * h)
    for y in range(h):
        for x in range(w):
            v = (x * 32 + y * 8) & 0xFF
            off = y * stride + x * 4
            buf[off:off + 4] = bytes((v, v ^ 0xFF, (v + y) & 0xFF, 0xFF))
    img = QtGui.QImage(bytes(buf), w, h, stride,
                       QtGui.QImage.Format.Format_RGB32)
    return img, buf


class TestEnsurePacked:
    def test_packed_passes_through(self):
        img = QtGui.QImage(8, 4, QtGui.QImage.Format.Format_RGB32)
        img.fill(0xFF112233)
        out = ensure_packed_rgb32(img)
        assert out.bytesPerLine() == 8 * 4
        assert out.pixel(3, 2) == img.pixel(3, 2)

    def test_padded_gets_repacked(self):
        img, _keepalive = _padded_rgb32()
        assert img.bytesPerLine() == 40
        out = ensure_packed_rgb32(img)
        assert out.bytesPerLine() == 8 * 4
        for y in range(4):
            for x in range(8):
                assert out.pixel(x, y) == img.pixel(x, y)

    def test_other_format_converts(self):
        img = QtGui.QImage(8, 4, QtGui.QImage.Format.Format_RGB555)
        img.fill(0x7FFF)
        out = ensure_packed_rgb32(img)
        assert out.format() == QtGui.QImage.Format.Format_RGB32
        assert out.bytesPerLine() == 8 * 4

    def test_null_safe(self):
        null = QtGui.QImage()
        assert ensure_packed_rgb32(null).isNull()
