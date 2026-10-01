"""Video frame helpers: stride guard for GDI painting.

Qt imports are lazy (inside functions) so this module stays importable
headless. GDI StretchDIBits assumes tightly packed rows, but decoder
frames sometimes arrive with padded scanlines - painting those paints
sheared bands. Repack when the stride does not match width*4.
"""

from __future__ import annotations

from wallmotion.utils import debug_log


def ensure_packed_rgb32(img):
    """RGB32 image with tight stride, or the input when already fine."""
    try:
        from PySide6.QtGui import QImage, QPainter
    except Exception:
        return img
    try:
        if img is None or bool(img.isNull()):
            return img
        if img.format() != QImage.Format.Format_RGB32:
            img = img.convertToFormat(QImage.Format.Format_RGB32)
        sw, sh = int(img.width()), int(img.height())
        if sw <= 0 or sh <= 0:
            return img
        if int(img.bytesPerLine()) == sw * 4:
            return img
        packed = QImage(sw, sh, QImage.Format.Format_RGB32)
        if packed.isNull():
            return img
        painter = QPainter(packed)
        try:
            painter.drawImage(0, 0, img)
        finally:
            try:
                painter.end()
            except Exception:
                pass
        debug_log(f"FRAME: repacked stride to {packed.bytesPerLine()}")
        return packed
    except Exception as e:
        debug_log(f"FRAME: repack failed: {e!r}")
        return img
