import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSlider, QFileDialog, QLabel)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
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
        
        # --- 第一行：進度條 ---
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
        
        # --- 第二行：控制按鈕 ---
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
        self.hide_timer.start(3000) # 縮短為 3 秒隱藏

    def syncPosition(self):
        screen = self.player.screen()
        geom = screen.geometry()
        self.setFixedWidth(geom.width())
        self.move(geom.x(), geom.bottom() - 150)

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini Pro Player")
        self.resize(1150, 750)
        
        self.is_mini_mode = False
        self.old_geometry = None
        self.playlist = []
        self.current_index = -1

        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)

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
        self.videoWidget = QVideoWidget()
        
        self.videoLayout.addWidget(self.leftSide)
        self.videoLayout.addWidget(self.videoWidget, 1)
        self.videoLayout.addWidget(self.rightSide)

        self.mediaPlayer.setVideoOutput(self.videoWidget)
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

        self.setupShortcuts()
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.playbackStateChanged.connect(self.updateButtons)
        self.loadAppIcon()

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
        self.volSlider.setRange(0, 100)
        self.volSlider.setValue(70)
        self.volSlider.setFixedWidth(100)
        self.volSlider.valueChanged.connect(self.setVolume)
        volume.addWidget(self.volLbl)
        volume.addWidget(self.volSlider)

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
            fileName = os.path.normpath(fileName).replace('\\', '/')
            self.updatePlaylist(fileName)
            self.mediaPlayer.setSource(QUrl.fromLocalFile(fileName))
            self.mediaPlayer.play()
            self.setWindowTitle(f"Gemini Pro Player - {os.path.basename(fileName)}")

    def updatePlaylist(self, currentFile):
        dir_path = os.path.dirname(os.path.abspath(currentFile))
        exts = ('.mp4', '.mkv', '.avi', '.mov', '.wmv')
        try:
            self.playlist = sorted([os.path.join(dir_path, f).replace('\\', '/') for f in os.listdir(dir_path) if f.lower().endswith(exts)])
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
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def updateButtons(self, state):
        txt = "⏸" if state == QMediaPlayer.PlaybackState.PlayingState else "▶"
        self.playBtn.setText(txt)
        self.fs_overlay.playBtn.setText(txt)

    def positionChanged(self, p):
        if not self.slider.isSliderDown(): self.slider.setValue(p)
        if not self.fs_overlay.slider.isSliderDown(): self.fs_overlay.slider.setValue(p)
        time_str = self.formatTime(p)
        self.currTimeLbl.setText(time_str); self.fs_overlay.currLbl.setText(time_str)

    def durationChanged(self, d):
        self.slider.setRange(0, d); self.fs_overlay.slider.setRange(0, d)
        total_str = self.formatTime(d); self.totalTimeLbl.setText(total_str); self.fs_overlay.totalLbl.setText(total_str)

    def setPosition(self, p): self.mediaPlayer.setPosition(p)
    def seekRelative(self, ms): self.mediaPlayer.setPosition(max(0, min(self.mediaPlayer.position() + ms, self.mediaPlayer.duration())))
    def setVolume(self, v): self.audioOutput.setVolume(v / 100); self.volLbl.setText("🔊" if v > 0 else "🔇")
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
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path); self.setWindowIcon(icon); QApplication.setWindowIcon(icon)

    def closeEvent(self, event):
        self.fs_overlay.close(); super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    if len(sys.argv) > 1: player.loadVideo(sys.argv[1])
    sys.exit(app.exec())
