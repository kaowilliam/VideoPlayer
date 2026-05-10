import sys
import os

# Add VLC path to environment for python-vlc to find DLLs
if sys.platform == "win32":
    import winreg
    def find_vlc():
        paths = []
        for key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                reg = winreg.OpenKey(key, r"SOFTWARE\VideoLAN\VLC")
                path, _ = winreg.QueryValueEx(reg, "InstallDir")
                paths.append(path)
            except: pass
        # Common default paths as fallback
        paths.extend([r"C:\Program Files\VideoLAN\VLC", r"C:\Program Files (x86)\VideoLAN\VLC"])
        for p in paths:
            if os.path.exists(os.path.join(p, "libvlc.dll")):
                os.add_dll_directory(p)
                return p
        return None
    vlc_path = find_vlc()

import vlc
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSlider, QFileDialog, QLabel)
from PyQt6.QtCore import Qt, QUrl, QPoint, QTimer, QRect, QEvent
from PyQt6.QtGui import QShortcut, QKeySequence, QMouseEvent, QIcon, QCursor

class ClickableSlider(QSlider):
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)

class SideBarBtn(QPushButton):
    def __init__(self, text, slot):
        super().__init__(text)
        self.setFixedWidth(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(slot)
        self.setStyleSheet("""
            QPushButton {
                background-color: #000000;
                color: rgba(255, 255, 255, 30);
                font-size: 30px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #1A1A1A;
                color: #00ADB5;
            }
        """)

class FullscreenOverlay(QWidget):
    def __init__(self, player):
        super().__init__(None)
        self.player = player
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(120)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 0, 40, 0)
        
        self.bg = QWidget(self)
        self.bg.setStyleSheet("background-color: rgba(20, 20, 20, 220); border-radius: 20px; border: 1px solid rgba(255,255,255,40);")
        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setContentsMargins(20, 10, 20, 10)
        
        prog_layout = QHBoxLayout()
        self.currLbl = QLabel("00:00")
        self.totalLbl = QLabel("00:00")
        self.currLbl.setStyleSheet("color: #00ADB5; font-size: 14px; font-weight: bold; background: transparent;")
        self.totalLbl.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: transparent;")
        
        self.slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider.setStyleSheet("""
            QSlider { background: transparent; height: 20px; }
            QSlider::groove:horizontal { height: 6px; background: rgba(255,255,255,40); border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #00ADB5; border-radius: 3px; }
            QSlider::handle:horizontal { background: white; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
        """)
        self.slider.sliderMoved.connect(self.player.setPosition)
        
        prog_layout.addWidget(self.currLbl)
        prog_layout.addWidget(self.slider)
        prog_layout.addWidget(self.totalLbl)
        bg_layout.addLayout(prog_layout)
        
        btns_layout = QHBoxLayout()
        btns_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btns_layout.setSpacing(30)
        
        self.backBtn = self.createOverlayBtn("⏪", lambda: self.player.seekRelative(-5000))
        self.playBtn = self.createOverlayBtn("▶", self.player.playVideo)
        self.fwdBtn = self.createOverlayBtn("⏩", lambda: self.player.seekRelative(5000))
        
        self.playBtn.setFixedSize(50, 50)
        self.playBtn.setStyleSheet(self.playBtn.styleSheet() + "font-size: 24px; border-radius: 25px; background-color: rgba(0, 173, 181, 180);")
        
        btns_layout.addWidget(self.backBtn)
        btns_layout.addWidget(self.playBtn)
        btns_layout.addWidget(self.fwdBtn)
        bg_layout.addLayout(btns_layout)
        
        main_layout.addWidget(self.bg)
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def createOverlayBtn(self, text, slot):
        btn = QPushButton(text)
        btn.setFixedSize(40, 40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 60, 150);
                color: white;
                border-radius: 20px;
                font-size: 18px;
                border: 1px solid rgba(255, 255, 255, 30);
            }
            QPushButton:hover { background-color: rgba(100, 100, 100, 200); }
        """)
        return btn

    def show_temporarily(self):
        if not self.player.isFullScreen(): return
        self.syncPosition()
        if not self.isVisible(): self.show()
        self.raise_()
        self.hide_timer.start(3000)

    def syncPosition(self):
        screen = self.player.screen()
        geom = screen.geometry()
        self.setFixedWidth(geom.width())
        self.move(geom.x(), geom.bottom() - 150)

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini Pro Player (VLC)")
        self.resize(1150, 750)
        
        self.is_mini_mode = False
        self.old_geometry = None
        self.playlist = []
        self.current_index = -1

        # VLC Instance and Player
        self.vlc_instance = vlc.Instance()
        self.mediaPlayer = self.vlc_instance.media_player_new()

        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QVBoxLayout(self.centralWidget)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        self.videoArea = QWidget()
        self.videoLayout = QHBoxLayout(self.videoArea)
        self.videoLayout.setContentsMargins(0, 0, 0, 0)
        self.videoLayout.setSpacing(0)

        self.leftSide = SideBarBtn("❮", lambda: self.skipVideo(-1))
        self.rightSide = SideBarBtn("❯", lambda: self.skipVideo(1))
        self.videoWidget = QWidget() # No longer QVideoWidget, just a container
        self.videoWidget.setStyleSheet("background-color: black;")
        
        self.videoLayout.addWidget(self.leftSide)
        self.videoLayout.addWidget(self.videoWidget, 1)
        self.videoLayout.addWidget(self.rightSide)

        # Set VLC output to our widget
        if sys.platform == "win32":
            self.mediaPlayer.set_hwnd(self.videoWidget.winId())
        elif sys.platform == "darwin":
            self.mediaPlayer.set_nsobject(int(self.videoWidget.winId()))
        else:
            self.mediaPlayer.set_xwindow(int(self.videoWidget.winId()))

        self.fs_overlay = FullscreenOverlay(self)

        self.setupControls()
        self.mainLayout.addWidget(self.videoArea, 1)
        self.mainLayout.addWidget(self.controlsPanel)

        self.videoWidget.setMouseTracking(True)
        self.videoWidget.installEventFilter(self)

        self.mouse_monitor_timer = QTimer()
        self.mouse_monitor_timer.timeout.connect(self.monitor_mouse_fullscreen)
        self.mouse_monitor_timer.start(250) 
        self.last_mouse_pos = QPoint()

        self.ui_update_timer = QTimer()
        self.ui_update_timer.setInterval(200)
        self.ui_update_timer.timeout.connect(self.updateUI)
        self.ui_update_timer.start()

        self.setupShortcuts()
        self.loadAppIcon()

    def updateUI(self):
        if self.mediaPlayer.is_playing() or True:
            # Sync Slider
            length = self.mediaPlayer.get_length()
            if length > 0:
                pos = self.mediaPlayer.get_time()
                if not self.slider.isSliderDown():
                    self.slider.setRange(0, length)
                    self.slider.setValue(pos)
                if not self.fs_overlay.slider.isSliderDown():
                    self.fs_overlay.slider.setRange(0, length)
                    self.fs_overlay.slider.setValue(pos)
                
                time_str = self.formatTime(pos)
                total_str = self.formatTime(length)
                self.currTimeLbl.setText(time_str)
                self.totalTimeLbl.setText(total_str)
                self.fs_overlay.currLbl.setText(time_str)
                self.fs_overlay.totalLbl.setText(total_str)
            
            # Sync Play Button
            state = self.mediaPlayer.get_state()
            txt = "⏸" if state == vlc.State.Playing else "▶"
            self.playBtn.setText(txt)
            self.fs_overlay.playBtn.setText(txt)

    def monitor_mouse_fullscreen(self):
        if self.isFullScreen():
            current_pos = QCursor.pos()
            if current_pos != self.last_mouse_pos:
                self.fs_overlay.show_temporarily()
                self.last_mouse_pos = current_pos

    def setupControls(self):
        self.controlsPanel = QWidget()
        self.controlsPanel.setFixedHeight(130)
        layout = QVBoxLayout(self.controlsPanel)
        layout.setContentsMargins(20, 10, 20, 15)
        
        prog = QHBoxLayout()
        self.currTimeLbl = QLabel("00:00")
        self.totalTimeLbl = QLabel("00:00")
        self.slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider.sliderMoved.connect(self.setPosition)
        prog.addWidget(self.currTimeLbl)
        prog.addWidget(self.slider)
        prog.addWidget(self.totalTimeLbl)
        layout.addLayout(prog)

        btns = QHBoxLayout()
        btns.setSpacing(15)
        self.openBtn = self.createIconButton("📂 開啟", self.openFile)
        self.prevBtn = self.createIconButton("⏮", lambda: self.skipVideo(-1))
        self.backBtn = self.createIconButton("⏪", lambda: self.seekRelative(-5000))
        self.playBtn = self.createIconButton("▶", self.playVideo)
        self.fwdBtn = self.createIconButton("⏩", lambda: self.seekRelative(5000))
        self.nextBtn = self.createIconButton("⏭", lambda: self.skipVideo(1))
        self.miniBtn = self.createIconButton("📺 小窗", self.toggleMiniPlayer)
        
        self.playBtn.setFixedSize(55, 55)
        self.playBtn.setStyleSheet("background-color: #00ADB5; color: white; font-size: 24px; border-radius: 27px;")
        
        volume = QHBoxLayout()
        self.volLbl = QLabel("🔊")
        self.volSlider = QSlider(Qt.Orientation.Horizontal)
        self.volSlider.setRange(0, 600)
        self.volSlider.setValue(100)
        self.volSlider.setFixedWidth(120)
        self.volSlider.valueChanged.connect(self.setVolume)
        self.volPercLbl = QLabel("100%")
        self.volPercLbl.setFixedWidth(40)
        
        volume.addWidget(self.volLbl)
        volume.addWidget(self.volSlider)
        volume.addWidget(self.volPercLbl)

        btns.addWidget(self.openBtn)
        btns.addStretch(1)
        btns.addWidget(self.prevBtn)
        btns.addWidget(self.backBtn)
        btns.addWidget(self.playBtn)
        btns.addWidget(self.fwdBtn)
        btns.addWidget(self.nextBtn)
        btns.addStretch(1)
        btns.addWidget(self.miniBtn)
        btns.addLayout(volume)
        layout.addLayout(btns)
        self.applyModernStyle()

    def applyModernStyle(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #000000; }
            QWidget { background-color: #1A1A1A; color: #FFFFFF; font-family: 'Segoe UI'; }
            QPushButton { background-color: #2D2D2D; border: none; padding: 5px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #3D3D3D; }
            QSlider::groove:horizontal { height: 4px; background: #333333; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #00ADB5; border-radius: 2px; }
            QSlider::handle:horizontal { background: #FFFFFF; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QLabel { font-size: 12px; color: #AAAAAA; }
        """)

    def eventFilter(self, obj, event):
        if obj == self.videoWidget:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.playVideo()
        return super().eventFilter(obj, event)

    def openFile(self):
        f, _ = QFileDialog.getOpenFileName(self, "選取影片", "", "Videos (*.mp4 *.mkv *.avi *.mov *.wmv)")
        if f: self.loadVideo(f)

    def loadVideo(self, fileName):
        if fileName:
            fileName = os.path.normpath(fileName)
            self.updatePlaylist(fileName)
            media = self.vlc_instance.media_new(fileName)
            self.mediaPlayer.set_media(media)
            self.mediaPlayer.play()
            self.setWindowTitle(f"Gemini Pro Player - {os.path.basename(fileName)}")
            # VLC requires a moment to start playback before volume/position can be set
            QTimer.singleShot(100, lambda: self.setVolume(self.volSlider.value()))

    def updatePlaylist(self, currentFile):
        dir_path = os.path.dirname(os.path.abspath(currentFile))
        exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
        try:
            self.playlist = sorted([os.path.join(dir_path, f) for f in os.listdir(dir_path) if f.lower().endswith(exts)])
            self.current_index = self.playlist.index(currentFile) if currentFile in self.playlist else -1
            has_multi = len(self.playlist) > 1
            self.leftSide.setVisible(has_multi)
            self.rightSide.setVisible(has_multi)
        except: pass

    def skipVideo(self, direction):
        if self.playlist and self.current_index != -1:
            idx = (self.current_index + direction) % len(self.playlist)
            self.loadVideo(self.playlist[idx])

    def playVideo(self):
        if self.mediaPlayer.is_playing():
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def setPosition(self, p): 
        self.mediaPlayer.set_time(p)

    def seekRelative(self, ms): 
        new_pos = max(0, min(self.mediaPlayer.get_time() + ms, self.mediaPlayer.get_length()))
        self.mediaPlayer.set_time(new_pos)
    
    def setVolume(self, v):
        # VLC audio_set_volume accepts 0-100 as normal, but internally supports software gain
        self.mediaPlayer.audio_set_volume(v)
        self.volPercLbl.setText(f"{v}%")
        if v == 0:
            self.volLbl.setText("🔇")
        elif v <= 100:
            self.volLbl.setText("🔊")
        else:
            self.volLbl.setText("🔥")

    def formatTime(self, ms):
        s, m, h = (ms // 1000) % 60, (ms // 60000) % 60, (ms // 3600000)
        return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"

    def toggleMiniPlayer(self):
        if not self.is_mini_mode:
            self.old_geometry = self.geometry(); self.is_mini_mode = True; self.controlsPanel.hide()
            self.leftSide.hide(); self.rightSide.hide()
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
            self.resize(360, 202); self.show(); self.activateWindow(); self.raise_()
        else: self.exitSpecialModes()

    def toggleFullscreen(self):
        if self.isFullScreen(): self.exitSpecialModes()
        else:
            self.old_geometry = self.geometry(); self.controlsPanel.hide()
            self.leftSide.hide(); self.rightSide.hide(); self.showFullScreen()

    def exitSpecialModes(self):
        self.is_mini_mode = False
        self.setWindowFlags(Qt.WindowType.Window)
        self.showNormal()
        self.controlsPanel.show()
        if len(self.playlist) > 1: self.leftSide.show(); self.rightSide.show()
        if self.old_geometry: self.setGeometry(self.old_geometry)
        self.show()
        self.activateWindow(); self.raise_(); self.fs_overlay.hide()
        QTimer.singleShot(100, self.showNormal)

    def createIconButton(self, t, s):
        b = QPushButton(t); b.clicked.connect(s); b.setFocusPolicy(Qt.FocusPolicy.NoFocus); return b

    def setupShortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.playVideo)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.seekRelative(-5000))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.seekRelative(5000))
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Left), self, lambda: self.skipVideo(-1))
        QShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Right), self, lambda: self.skipVideo(1))
        QShortcut(QKeySequence(Qt.Key.Key_F), self, self.toggleFullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_P), self, self.toggleMiniPlayer)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.exitSpecialModes)

    def loadAppIcon(self):
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "icon.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
            QApplication.setWindowIcon(icon)

    def closeEvent(self, event):
        # Stop all timers first to prevent them from calling methods on a half-destroyed object
        if hasattr(self, "ui_update_timer"):
            self.ui_update_timer.stop()
        if hasattr(self, "mouse_monitor_timer"):
            self.mouse_monitor_timer.stop()
        if hasattr(self, "hide_timer"):
            self.hide_timer.stop()
            
        # Stop playback and release VLC resources
        if hasattr(self, "mediaPlayer"):
            self.mediaPlayer.stop()
            self.mediaPlayer.release()
        if hasattr(self, "vlc_instance"):
            self.vlc_instance.release()
            
        self.fs_overlay.close()
        super().closeEvent(event)

def register_app():
    if sys.platform == 'win32':
        import winreg
        exe_path = os.path.abspath(sys.argv[0])
        exe_name = os.path.basename(exe_path)
        try:
            # Register in HKCU\Software\Classes\Applications so Windows recognizes it as a valid handler
            app_key = rf"Software\Classes\Applications\{exe_name}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key) as key:
                winreg.SetValueEx(key, "FriendlyAppName", 0, winreg.REG_SZ, "Gemini Pro Player")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{app_key}\SupportedTypes") as key:
                for ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']:
                    winreg.SetValueEx(key, ext, 0, winreg.REG_SZ, "")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{app_key}\shell\open\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')
        except Exception:
            pass

if __name__ == "__main__":
    register_app()
    if sys.platform == 'win32':
        import ctypes
        myappid = 'gemini.pro.player.1.0' # arbitrary string
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    if len(sys.argv) > 1: player.loadVideo(sys.argv[1])
    sys.exit(app.exec())
