import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from karcytics.ui.theme import Colors, Fonts, get_tamil_font_family, theme_manager


class ProgrammaticLoader(QWidget):
    """A high-drama, transparent 3D DNA helix with absorbed binary data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(250, 250)

        self.angle = 0.0
        self.pulse = 0.0

        self.binary_bits = []
        for _ in range(12):
            self.binary_bits.append(self._make_bit(stagger=True))

        self.dust = []
        for _ in range(25):
            self.dust.append(
                {
                    "x": random.uniform(0, 1),
                    "y": random.uniform(0, 1),
                    "size_mult": random.uniform(0.5, 1.2),
                    "flicker": random.uniform(0, math.pi),
                }
            )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(16)

    def _make_bit(self, stagger=False):
        """Create a stream with theme-aware characters."""
        from_top = random.random() < 0.5
        x = random.uniform(0.05, 0.95)

        if stagger:
            y = random.uniform(-0.1, 0.60) if from_top else random.uniform(0.40, 1.10)
        else:
            y = -0.05 if from_top else 1.05

        return {
            "x": x,
            "y": y,
            "from_top": from_top,
            "speed": random.uniform(0.002, 0.004) * (1 if from_top else -1),
            "x_drift": (0.5 - x) * random.uniform(0.002, 0.006),
            # ── THE FIX: Use the dynamic glyph pool ──
            "chars": [random.choice(self._glyph_pool) for _ in range(random.randint(2, 4))],
            "base_alpha": random.randint(80, 130),
        }

    @property
    def _is_tamil_active(self) -> bool:
        """True when the default theme is active (Tamil numerals replace binary)."""
        return theme_manager.current_theme_name == "Karcytics Default"

    @property
    def _glyph_pool(self) -> list[str]:
        """Returns Tamil numerals on the default theme, aggressive glyphs for
        Dark Side, or binary everywhere else."""
        # Using .upper() to ensure the hex comparison is bulletproof
        is_dark_side = getattr(Colors, "DNA_PRIMARY", "").upper() == "#E60000"
        if is_dark_side:
            # Aggressive Sith/Imperial Style Glyphs
            return ["ᚙ", "ᚘ", "ᚕ", "ᚖ", "ᚗ", "ᚠ", "ᚥ", "ᚻ", "◢", "◥", "▚", "▞"]
        if self._is_tamil_active:
            # Tamil numerals 0 and 1 (௦ / ௧) stand in for binary
            return ["௦", "௧"]
        return ["0", "1"]

    def _update_animation(self):
        """
        Advances the loader animation and updates the binary stream states.

        Refreshes glyphs when the active theme changes, moves streams, reinitializes absorbed or off-screen streams, applies occasional flicker, and schedules the widget for repainting.
        """
        self.angle += 0.025
        self.pulse = math.sin(self.angle * 0.8) * 0.1

        pool = self._glyph_pool

        for b in self.binary_bits:
            # ── THE INSTANT SWAP FIX ──
            # If the bit's current characters aren't in the active pool,
            # it means the theme just changed. Force an instant refresh of this bit.
            if b["chars"] and b["chars"][0] not in pool:
                b["chars"] = [random.choice(pool) for _ in range(len(b["chars"]))]
            # ──────────────────────────

            b["y"] += b["speed"]
            b["x"] += b["x_drift"]

            absorbed = (b["from_top"] and b["y"] > 0.60) or (not b["from_top"] and b["y"] < 0.40)
            off_screen = b["y"] < -0.1 or b["y"] > 1.1

            if absorbed or off_screen:
                b.update(self._make_bit(stagger=False))

            # Normal flickering logic
            if random.random() < 0.08:
                idx = random.randint(0, len(b["chars"]) - 1)
                b["chars"][idx] = random.choice(pool)

        self.update()

    def paintEvent(self, event):  # noqa: ARG002, N802
        """
        Render the animated binary streams, embers, and DNA helix.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        unit = min(w, h) / 100.0

        # Pull live colors from theme (Fallback to original Cyan/Purple)
        color_primary = getattr(Colors, "DNA_PRIMARY", "#00f2ff")
        color_secondary = getattr(Colors, "DNA_SECONDARY", "#a371f7")

        # --- LAYER 1: BINARY STREAMS (top + bottom) ---
        font_size = max(8, int(5.5 * unit))
        if self._is_tamil_active:
            # Bundled Tamil font, scoped to just these glyphs — FAMILY_MONO
            # doesn't carry Tamil script and shouldn't change for the rest of the app.
            painter.setFont(QFont(get_tamil_font_family(), font_size, QFont.Weight.Bold))
        else:
            painter.setFont(QFont(Fonts.FAMILY_MONO, font_size, QFont.Weight.Bold))

        for b in self.binary_bits:
            y_norm = b["y"]
            # Adjust progress math to match the new 0.60/0.40 absorption points
            progress = y_norm / 0.60 if b["from_top"] else (1.0 - y_norm) / 0.60
            progress = max(0.0, min(1.0, progress))

            fade_in = min(1.0, progress / 0.20)
            fade_out = max(0.0, 1.0 - max(0.0, progress - 0.75) / 0.25)
            master_alpha = b["base_alpha"] * fade_in * fade_out

            if master_alpha < 2:
                continue

            char_x = b["x"] * w
            char_y = b["y"] * h
            trail_dy = -math.copysign(font_size * 1.4, b["speed"])

            for i, char in enumerate(b["chars"]):
                cy_char = char_y + trail_dy * i
                taper = 1.0 - (i / len(b["chars"])) * 0.85
                alpha = int(master_alpha * taper)
                if alpha <= 0:
                    continue

                c_stream = QColor(color_secondary)
                c_stream.setAlpha(alpha)
                painter.setPen(c_stream)
                painter.drawText(QPointF(char_x, cy_char), char)

        # --- LAYER 2: DUST / SITH EMBERS ---
        is_dark_side = getattr(Colors, "DNA_PRIMARY", "").upper() == "#E60000"

        for d in self.dust:
            # ── THE SITH UPGRADE: Rising Embers ──
            # In Galactic mode, we add a vertical drift so they float upward
            y_pos = d["y"]
            if is_dark_side:
                # Subtracting from Y makes them rise; modulo % 1.0 wraps them back to the bottom
                y_pos = (d["y"] - self.angle * 0.08) % 1.0

            # Flicker intensity
            alpha = int(40 + 30 * math.sin(self.angle * 3 + d["flicker"]))

            c_dust = QColor(color_primary)
            c_dust.setAlpha(alpha)
            painter.setBrush(c_dust)
            painter.setPen(Qt.PenStyle.NoPen)

            # Size math
            s = 1.2 * unit * d["size_mult"]

            if is_dark_side:
                # 1. Draw as glowing circular sparks
                painter.drawEllipse(QRectF(d["x"] * w, y_pos * h, s, s))

                # 2. Add a tiny "hot core" for the embers
                core_color = QColor("#ffffff")
                core_color.setAlpha(int(alpha * 0.6))
                painter.setBrush(core_color)
                painter.drawEllipse(
                    QRectF(d["x"] * w + s * 0.25, y_pos * h + s * 0.25, s * 0.5, s * 0.5)
                )

                # Reset brush for next iteration
                painter.setBrush(c_dust)
            else:
                # Draw as standard digital squares for the Default theme
                painter.drawRect(QRectF(d["x"] * w, y_pos * h, s, s))
        # --- LAYER 3: THE HELIX MATH ---
        scale_mod = 1.0 + self.pulse
        base_spacing = 5.0 * unit

        # ── THE FIX: Shrink helix height to 60% of widget to create safe buffer ──
        target_helix_height = min(w, h) * 0.60

        num_bases = max(8, int(target_helix_height / base_spacing))
        spacing = base_spacing * scale_mod
        amplitude = min(w, h) * 0.18 * scale_mod

        twist = 0.40
        start_y = cy - (num_bases * spacing) / 2

        points = []
        for i in range(num_bases):
            y = start_y + i * spacing
            p1 = self.angle + (i * twist)
            dist_from_center = abs(y - cy)

            # ── THE FIX: Tighten fade boundary and sharpen falloff curve ──
            # fade_boundary is now 1.15x the helix radius (was 1.35x)
            # Power of 2.5 ensures transparency hits 0 before the physical edge
            max_dist = (num_bases * spacing) / 2.0
            fade_boundary = max_dist * 1.15
            fade = max(0.0, 1.0 - (dist_from_center / fade_boundary) ** 2.5)

            points.append(
                {
                    "y": y,
                    "x1": cx + math.sin(p1) * amplitude,
                    "z1": math.cos(p1),
                    "x2": cx + math.sin(p1 + math.pi) * amplitude,
                    "z2": math.cos(p1 + math.pi),
                    "fade": fade,
                }
            )

        # Back nodes
        for p in points:
            self._draw_node(
                painter, p["x1"], p["y"], p["z1"], color_primary, unit, False, p["fade"]
            )
            self._draw_node(
                painter, p["x2"], p["y"], p["z2"], color_secondary, unit, False, p["fade"]
            )

        # Rungs
        for p in points:
            pen = QPen()
            pen.setWidthF(1.2 * unit)
            grad = QLinearGradient(p["x1"], p["y"], p["x2"], p["y"])
            base_alpha = 100 + (p["z1"] + p["z2"]) * 25
            alpha = int(base_alpha * p["fade"])
            c1, c2 = QColor(color_primary), QColor(color_secondary)
            c1.setAlpha(alpha)
            c2.setAlpha(alpha)
            grad.setColorAt(0.2, c1)
            grad.setColorAt(0.8, c2)
            pen.setBrush(grad)
            painter.setPen(pen)
            painter.drawLine(QPointF(p["x1"], p["y"]), QPointF(p["x2"], p["y"]))

        # Front nodes
        for p in points:
            self._draw_node(painter, p["x1"], p["y"], p["z1"], color_primary, unit, True, p["fade"])
            self._draw_node(
                painter, p["x2"], p["y"], p["z2"], color_secondary, unit, True, p["fade"]
            )

    def _draw_node(self, painter, x, y, z, color_str, unit, is_front, fade):
        if (is_front and z < 0) or (not is_front and z >= 0):
            return

        size = (4.0 * unit) * (1.2 + z * 0.4)
        color = QColor(color_str)

        # Glow logic
        # Start glowing slightly when it's still in the back (z > -0.5)
        glow_intensity = max(0.0, z + 0.5)
        if glow_intensity > 0:
            # Outer bloom — wide, soft halo
            glow_radius = size * 2.5
            glow = QRadialGradient(x, y, glow_radius)
            gc = QColor(color)
            gc.setAlpha(int(70 * glow_intensity * fade))
            glow.setColorAt(0, gc)
            glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                QRectF(x - glow_radius, y - glow_radius, glow_radius * 2, glow_radius * 2)
            )

            # Inner bloom — tight hot core
            inner_radius = size * 2.0
            inner_glow = QRadialGradient(x, y, inner_radius)
            ic = QColor(color)
            ic.setAlpha(int(100 * glow_intensity * fade))
            inner_glow.setColorAt(0, ic)
            inner_glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(inner_glow)
            painter.drawEllipse(
                QRectF(x - inner_radius, y - inner_radius, inner_radius * 2, inner_radius * 2)
            )

        # Body logic
        # Blend between flat color (back) and 3D sphere gradient (front)
        sphere_blend = max(0.0, min(1.0, (z + 0.5) / 1.0))

        flat_alpha = int((60 + (z + 1) * 30) * fade)
        sphere_alpha = int(255 * fade)

        c0_flat = QColor(color)
        c0_flat.setAlpha(flat_alpha)
        c0_sphere = QColor(255, 255, 255, sphere_alpha)

        c3_flat = QColor(color)
        c3_flat.setAlpha(flat_alpha)
        c3_sphere = QColor(color)
        c3_sphere.setAlpha(sphere_alpha)

        c1_flat = QColor(color)
        c1_flat.setAlpha(flat_alpha)
        c1_sphere = color.darker(150)
        c1_sphere.setAlpha(sphere_alpha)

        def blend_colors(c1, c2, factor):
            return QColor(
                int(c1.red() * (1 - factor) + c2.red() * factor),
                int(c1.green() * (1 - factor) + c2.green() * factor),
                int(c1.blue() * (1 - factor) + c2.blue() * factor),
                int(c1.alpha() * (1 - factor) + c2.alpha() * factor),
            )

        grad = QRadialGradient(x - size * 0.2, y - size * 0.2, size)
        grad.setColorAt(0, blend_colors(c0_flat, c0_sphere, sphere_blend))
        grad.setColorAt(0.3, blend_colors(c3_flat, c3_sphere, sphere_blend))
        grad.setColorAt(1, blend_colors(c1_flat, c1_sphere, sphere_blend))

        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(x - size / 2, y - size / 2, size, size))
