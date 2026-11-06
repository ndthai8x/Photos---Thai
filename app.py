import sys
import os
import json
import re
import random
import requests
import winreg
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QRect, QParallelAnimationGroup
from PyQt6.QtGui import QPixmap, QImage, QAction, QActionGroup, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QMenu, QInputDialog, 
    QMessageBox, QGraphicsOpacityEffect
)

DEFAULT_URL = "https://photos.app.goo.gl/oyRNUixqBg8Zc3ueA"
CONFIG_FILE = "settings.json"
APP_NAME = "GooglePhotosSlideshow"

TRANSITIONS = [
    "Random (Ngẫu nhiên)",
    "Fade (Mờ dần)",
    "Slide Left (Trượt trái)",
    "Slide Right (Trượt phải)",
    "Slide Up (Trượt lên)",
    "Slide Down (Trượt xuống)",
    "Zoom In (Phóng to)",
    "Zoom Out (Thu nhỏ)",
    "Fade & Slide (Trượt mờ)",
    "Curtain Reveal (Kéo rèm)",
    "Instant (Đổi tức thì)"
]

def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def load_settings():
    default_config = {
        "url": DEFAULT_URL,
        "interval": 5,
        "transition": "Random (Ngẫu nhiên)",
        "window_width": 480,
        "pos_x": 100,
        "pos_y": 100,
        "autostart": False
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config

def save_settings(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass

def set_autostart(enable):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        exe_path = f'"{sys.executable}"'
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Lỗi autostart: {e}")

def scrape_gphotos(album_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(album_url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        pattern = re.compile(r'https:\/\/lh3\.googleusercontent\.com\/pw\/[a-zA-Z0-9_\-]+')
        matches = list(set(pattern.findall(res.text)))
        if not matches:
            pattern_alt = re.compile(r'https:\/\/lh3\.googleusercontent\.com\/[a-zA-Z0-9_\-]+')
            matches = list(set(pattern_alt.findall(res.text)))
        valid_urls = [u for u in matches if not any(x in u for x in ["=s", "=w", "=h"])]
        return valid_urls
    except Exception as e:
        print(f"Lỗi tải album: {e}")
        return []

class SlideshowApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_settings()
        self.image_urls = []
        self.current_idx = -1
        self.drag_pos = QPoint()

        icon_path = os.path.join(get_base_path(), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.lbl_curr = QLabel(self)
        self.lbl_next = QLabel(self)
        self.lbl_curr.setScaledContents(True)
        self.lbl_next.setScaledContents(True)
        self.lbl_next.hide()

        self.anim_group = None

        self.target_width = self.cfg.get("window_width", 480)
        self.move(self.cfg.get("pos_x", 100), self.cfg.get("pos_y", 100))
        self.resize(self.target_width, int(self.target_width * 9 / 16))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.display_next_image)

        self.fetch_images()

    def fetch_images(self):
        urls = scrape_gphotos(self.cfg["url"])
        if urls:
            self.image_urls = urls
            self.current_idx = -1
            self.start_timer()
            self.display_next_image()
        else:
            self.lbl_curr.setText("Không tìm thấy ảnh hoặc link lỗi.\nChuột phải -> Chọn 'Đổi link Album Google Photos'")
            self.lbl_curr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lbl_curr.setStyleSheet("color: red; background: #222; font-size: 14px;")

    def start_timer(self):
        self.timer.stop()
        self.timer.start(int(self.cfg["interval"] * 1000))

    def load_pixmap_from_url(self, url):
        try:
            req_url = f"{url}=w1920-h1080"
            r = requests.get(req_url, timeout=10)
            img = Image.open(BytesIO(r.content))
            img = img.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qim = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            return QPixmap.fromImage(qim)
        except Exception:
            return None

    def display_next_image(self):
        if not self.image_urls:
            return
        self.current_idx = (self.current_idx + 1) % len(self.image_urls)
        pix = self.load_pixmap_from_url(self.image_urls[self.current_idx])
        if not pix or pix.isNull():
            return

        w = pix.width()
        h = pix.height()
        target_h = int(self.target_width * (h / w))
        self.resize(self.target_width, target_h)
        self.lbl_curr.resize(self.target_width, target_h)
        self.lbl_next.resize(self.target_width, target_h)

        self.run_transition(pix)

    def run_transition(self, new_pixmap):
        mode = self.cfg["transition"]
        if mode == "Random (Ngẫu nhiên)":
            choices = [t for t in TRANSITIONS if "Random" not in t and "Instant" not in t]
            mode = random.choice(choices)

        if mode == "Instant (Đổi tức thì)" or self.lbl_curr.pixmap() is None:
            self.lbl_curr.setPixmap(new_pixmap)
            self.lbl_curr.show()
            self.lbl_next.hide()
            return

        self.lbl_next.setPixmap(new_pixmap)
        self.lbl_next.show()
        self.lbl_next.raise_()

        w, h = self.width(), self.height()
        self.anim_group = QParallelAnimationGroup()

        if mode == "Fade (Mờ dần)":
            eff = QGraphicsOpacityEffect(self.lbl_next)
            self.lbl_next.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity")
            anim.setDuration(800)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            self.anim_group.addAnimation(anim)

        elif mode == "Slide Left (Trượt trái)":
            self.lbl_next.setGeometry(w, 0, w, h)
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(600)
            anim.setStartValue(QRect(w, 0, w, h))
            anim.setEndValue(QRect(0, 0, w, h))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(anim)

        elif mode == "Slide Right (Trượt phải)":
            self.lbl_next.setGeometry(-w, 0, w, h)
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(600)
            anim.setStartValue(QRect(-w, 0, w, h))
            anim.setEndValue(QRect(0, 0, w, h))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(anim)

        elif mode == "Slide Up (Trượt lên)":
            self.lbl_next.setGeometry(0, h, w, h)
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(600)
            anim.setStartValue(QRect(0, h, w, h))
            anim.setEndValue(QRect(0, 0, w, h))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(anim)

        elif mode == "Slide Down (Trượt xuống)":
            self.lbl_next.setGeometry(0, -h, w, h)
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(600)
            anim.setStartValue(QRect(0, -h, w, h))
            anim.setEndValue(QRect(0, 0, w, h))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(anim)

        elif mode == "Zoom In (Phóng to)":
            self.lbl_next.setGeometry(int(w/2), int(h/2), 0, 0)
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(700)
            anim.setStartValue(QRect(int(w/2), int(h/2), 0, 0))
            anim.setEndValue(QRect(0, 0, w, h))
            anim.setEasingCurve(QEasingCurve.Type.OutBack)
            self.anim_group.addAnimation(anim)

        elif mode == "Zoom Out (Thu nhỏ)":
            self.lbl_next.setGeometry(-int(w*0.2), -int(h*0.2), int(w*1.4), int(h*1.4))
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(700)
            anim.setStartValue(QRect(-int(w*0.2), -int(h*0.2), int(w*1.4), int(h*1.4)))
            anim.setEndValue(QRect(0, 0, w, h))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(anim)

        elif mode == "Fade & Slide (Trượt mờ)":
            eff = QGraphicsOpacityEffect(self.lbl_next)
            self.lbl_next.setGraphicsEffect(eff)
            anim_fade = QPropertyAnimation(eff, b"opacity")
            anim_fade.setDuration(600)
            anim_fade.setStartValue(0.0)
            anim_fade.setEndValue(1.0)
            
            self.lbl_next.setGeometry(50, 0, w, h)
            anim_move = QPropertyAnimation(self.lbl_next, b"geometry")
            anim_move.setDuration(600)
            anim_move.setStartValue(QRect(50, 0, w, h))
            anim_move.setEndValue(QRect(0, 0, w, h))

            self.anim_group.addAnimation(anim_fade)
            self.anim_group.addAnimation(anim_move)

        elif mode == "Curtain Reveal (Kéo rèm)":
            self.lbl_next.setGeometry(0, 0, 0, h)
            anim = QPropertyAnimation(self.lbl_next, b"geometry")
            anim.setDuration(600)
            anim.setStartValue(QRect(0, 0, 0, h))
            anim.setEndValue(QRect(0, 0, w, h))
            self.anim_group.addAnimation(anim)

        def on_finished():
            self.lbl_curr.setPixmap(new_pixmap)
            self.lbl_curr.setGeometry(0, 0, w, h)
            self.lbl_next.hide()
            self.lbl_next.setGraphicsEffect(None)

        self.anim_group.finished.connect(on_finished)
        self.anim_group.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            self.cfg["pos_x"] = self.x()
            self.cfg["pos_y"] = self.y()
            save_settings(self.cfg)
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        act_url = QAction("Đổi link Album Google Photos", self)
        act_url.triggered.connect(self.action_change_url)
        menu.addAction(act_url)

        act_refresh = QAction("Làm mới danh sách ảnh (Reload)", self)
        act_refresh.triggered.connect(self.fetch_images)
        menu.addAction(act_refresh)

        menu.addSeparator()

        act_speed = QAction(f"Tốc độ chạy hình ({self.cfg['interval']}s)", self)
        act_speed.triggered.connect(self.action_change_speed)
        menu.addAction(act_speed)

        act_size = QAction(f"Độ rộng cửa sổ ({self.target_width}px)", self)
        act_size.triggered.connect(self.action_change_width)
        menu.addAction(act_size)

        menu_trans = menu.addMenu("Hiệu ứng chuyển cảnh")
        trans_group = QActionGroup(self)
        for t in TRANSITIONS:
            act_t = QAction(t, self, checkable=True)
            if t == self.cfg["transition"]:
                act_t.setChecked(True)
            act_t.triggered.connect(lambda chk, name=t: self.action_set_transition(name))
            trans_group.addAction(act_t)
            menu_trans.addAction(act_t)

        menu.addSeparator()

        act_auto = QAction("Khởi động cùng Windows", self, checkable=True)
        act_auto.setChecked(self.cfg.get("autostart", False))
        act_auto.triggered.connect(self.action_toggle_autostart)
        menu.addAction(act_auto)

        menu.addSeparator()

        act_exit = QAction("Thoát", self)
        act_exit.triggered.connect(self.close)
        menu.addAction(act_exit)

        menu.exec(event.globalPos())

    def action_change_url(self):
        new_url, ok = QInputDialog.getText(self, "Google Photos Album", "Nhập link Album công khai:", text=self.cfg["url"])
        if ok and new_url.strip():
            self.cfg["url"] = new_url.strip()
            save_settings(self.cfg)
            self.fetch_images()

    def action_change_speed(self):
        val, ok = QInputDialog.getInt(self, "Thời gian chuyển hình", "Số giây mỗi ảnh:", value=self.cfg["interval"], min=1, max=3600)
        if ok:
            self.cfg["interval"] = val
            save_settings(self.cfg)
            self.start_timer()

    def action_change_width(self):
        val, ok = QInputDialog.getInt(self, "Kích thước hiển thị", "Độ rộng cửa sổ (pixel):", value=self.target_width, min=200, max=3840)
        if ok:
            self.target_width = val
            self.cfg["window_width"] = val
            save_settings(self.cfg)
            self.display_next_image()

    def action_set_transition(self, name):
        self.cfg["transition"] = name
        save_settings(self.cfg)

    def action_toggle_autostart(self, state):
        self.cfg["autostart"] = state
        save_settings(self.cfg)
        set_autostart(state)

    def closeEvent(self, event):
        self.cfg["pos_x"] = self.x()
        self.cfg["pos_y"] = self.y()
        self.cfg["window_width"] = self.target_width
        save_settings(self.cfg)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SlideshowApp()
    window.show()
    sys.exit(app.exec())
