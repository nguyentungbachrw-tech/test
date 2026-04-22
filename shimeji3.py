#!/usr/bin/env python3
import sys
import os
import random
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QCoreApplication
from PySide6.QtGui import QPixmap, QGuiApplication, QAction, QTransform, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QMenu
import math
from collections import deque

# ---------------------------
# Config
# ---------------------------
SPRITES_DIR = Path(__file__).resolve().parent / "sprites"
IDLE_DIR = SPRITES_DIR / "idle"
WALK_DIR = SPRITES_DIR / "walk"

ANIM_FPS = 10
UPDATE_FPS = 60
GRAVITY = 1500.0
WALK_SPEED = 120.0
JUMP_VELOCITY = -600.0

BOUNCE_DAMPING = 0.6     # energy loss per bounce
MIN_BOUNCE_SPEED = 50    # stop bouncing if slower than this

# ---------------------------
# Utility: load frames
# ---------------------------
def load_frames(folder: Path):
    frames = []
    if not folder.exists():
        return frames
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
            pix = QPixmap(str(p))
            if not pix.isNull():
                frames.append(pix)
    return frames

# ---------------------------
# Shimeji widget
# ---------------------------
class Shimeji(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon("roland.png"))

        # load frames
        self.idle_frames = load_frames(IDLE_DIR)
        self.walk_frames = load_frames(WALK_DIR)

        # fallback if no sprites
        if not (self.idle_frames or self.walk_frames):
            p = QPixmap(128, 128)
            p.fill(Qt.transparent)
            from PySide6.QtGui import QPainter, QColor
            painter = QPainter(p)
            painter.setBrush(QColor(200, 100, 220, 200))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 128, 128)
            painter.end()
            self.idle_frames = [p]

        self.current_frames = self.idle_frames if self.idle_frames else self.walk_frames
        self.anim_index = 0

        # window config
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # label
        self.label = QLabel(self)
        self.label.setAttribute(Qt.WA_TranslucentBackground)
        self.label.setScaledContents(True)
        self.label.setFixedSize(self.current_frames[0].size())
        self.resize(self.label.size())

        # starting position
        screen = QGuiApplication.primaryScreen().availableGeometry()
        start_x = random.randint(screen.left(), max(screen.left(), screen.right() - self.width()))
        start_y = screen.top() + screen.height() // 4
        self.move(start_x, start_y)

        # physics
        self.vx = random.choice([-WALK_SPEED, WALK_SPEED])
        self.vy = 0.0
        self.on_ground = False
        self.facing_right = self.vx > 0

        # animation timers
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._advance_anim)
        self.anim_timer.start(int(1000 / ANIM_FPS))

        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_physics)
        self.update_timer.start(int(1000 / UPDATE_FPS))

        # dragging
        self.dragging = False
        self.drag_offset = QPoint(0, 0)

        # context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._update_pixmap()
        self.fling_mode = False
        self.friction = 1
        self.mouse_history = deque(maxlen=5)

    # ---------------------------
    # Animation
    # ---------------------------
    def _advance_anim(self):
        if not self.current_frames:
            return
        self.anim_index = (self.anim_index + 1) % len(self.current_frames)
        self._update_pixmap()

    def _update_pixmap(self):
        pix = self.current_frames[self.anim_index]
        if not self.facing_right:
            transform = QTransform().scale(-1, 1)
            pix = pix.transformed(transform)
        self.label.setPixmap(pix)
        self.label.setFixedSize(pix.size())
        self.resize(self.label.size())

    # ---------------------------
    # Physics & movement
    # ---------------------------
    def _update_physics(self):
        dt = 1.0 / UPDATE_FPS

        if self.dragging:
            return

        screen_geom: QRect = QGuiApplication.primaryScreen().availableGeometry()
        ground_y = screen_geom.bottom() - self.height()
        top_y = screen_geom.top()

        if self.fling_mode:
            # Gravity still applies during fling
            self.vy += GRAVITY * dt
            self.vx *= self.friction

            dx = self.vx * dt
            dy = self.vy * dt
            new_x = self.x() + int(dx)
            new_y = self.y() + int(dy)

            # Top collision bounce
            if new_y <= top_y:
                new_y = top_y
                self.vy = -self.vy * 1  # bounce with energy loss

            # Ground collision
            if new_y >= ground_y:
                new_y = ground_y
                self.vy = -self.vy * 1
                if abs(self.vy) < 25:
                    self.vy = 0
                    self.fling_mode = False
                    self.on_ground = True
                    self.vx = random.choice([-WALK_SPEED, WALK_SPEED])
                    self.facing_right = self.vx > 0
                else:
                    self.on_ground = False

            # Wall collision
            if new_x <= screen_geom.left():
                new_x = screen_geom.left()
                self.vx = abs(self.vx)
                self.facing_right = True
            elif new_x >= screen_geom.right() - self.width():
                new_x = screen_geom.right() - self.width()
                self.vx = -abs(self.vx)
                self.facing_right = False

            self.move(new_x, new_y)
            return

        # ---------- Normal walking physics ----------
        self.vy += GRAVITY * dt
        dx = self.vx * dt
        dy = self.vy * dt
        new_x = self.x() + int(dx)
        new_y = self.y() + int(dy)

        # Top collision bounce
        if new_y <= top_y:
            new_y = top_y
            self.vy = -self.vy * 1

        # Ground collision bounce
        if new_y >= ground_y:
            new_y = ground_y
            self.vy = -self.vy * 1
            if abs(self.vy) < 50:
                self.vy = 0
                self.on_ground = True
            else:
                self.on_ground = False

        # Wall collision + jump
        if new_x <= screen_geom.left():
            new_x = screen_geom.left()
            self.vx = abs(self.vx)
            self.facing_right = True
            if self.on_ground:
                self.vy = JUMP_VELOCITY * 0.4
        elif new_x >= screen_geom.right() - self.width():
            new_x = screen_geom.right() - self.width()
            self.vx = -abs(self.vx)
            self.facing_right = False
            if self.on_ground:
                self.vy = JUMP_VELOCITY * 0.4

        self.move(new_x, new_y)

        # Choose animation
        if abs(self.vx) > 1 and self.on_ground:
            if self.current_frames is not self.walk_frames and self.walk_frames:
                self.current_frames = self.walk_frames
                self.anim_index = 0
        else:
            if self.current_frames is not self.idle_frames and self.idle_frames:
                self.current_frames = self.idle_frames
                self.anim_index = 0

        if random.random() < 0.002:
            self.vx *= -1
            self.facing_right = self.vx > 0

    # ---------------------------
    # Mouse events
    # ---------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_offset = event.position().toPoint()
            self.vx = 0
            self.vy = 0
            self.mouse_history.clear()
            self.mouse_history.append((event.globalPosition().toPoint(), event.timestamp() / 1000.0))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            global_pos = event.globalPosition().toPoint()
            new_top_left = global_pos - self.drag_offset
            self.move(new_top_left)
            self.mouse_history.append((global_pos, event.timestamp() / 1000.0))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            if len(self.mouse_history) >= 2:
                pos_old, t_old = self.mouse_history[0]
                pos_new, t_new = self.mouse_history[-1]
                dt = max(t_new - t_old, 0.001)
                self.vx = (pos_new.x() - pos_old.x()) / dt
                self.vy = (pos_new.y() - pos_old.y()) / dt
            else:
                self.vx = self.vy = 0

            self.facing_right = self.vx > 0
            self.fling_mode = True
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    

    # ---------------------------
    # Context menu
    # ---------------------------
    def _show_context_menu(self, pos):
        menu = QMenu(self)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        menu.exec(self.mapToGlobal(pos))

# ---------------------------
# Main
# ---------------------------
def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    shimejis = []
    for i in range(2):  # spawn 3 total (1 original + 2 extra)
        s = Shimeji()
        s.setWindowTitle(f"Shimeji Bounce {i+1}")
        s.show()
        shimejis.append(s)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()