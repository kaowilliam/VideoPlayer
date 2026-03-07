import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSlider, QFileDialog, QLabel)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QPoint, QTimer, QRect, QEvent
from PyQt6.QtGui import QShortcut, QKeySequence, QMouseEvent, QIcon

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

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini Pro Player")
        self.resize(1150, 750)
        
        self.is_mini_mode = False
        self.old_geometry = None
        self.playlist = []
        self.current_index = -1

        # 1. 核心引擎
        self.mediaPlayer = QMediaPlayer()
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setAudioOutput(self.audioOutput)

        # 2. UI 結構
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QVBoxLayout(self.centralWidget)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)

        # --- 影片區域 (含左右導航) ---
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
        # ---------------------------

        self.mediaPlayer.setVideoOutput(self.videoWidget)

        # 3. 下方控制面板
        self.setupControls()

        # 組裝主佈局
        self.mainLayout.addWidget(self.videoArea, 1)
        self.mainLayout.addWidget(self.controlsPanel)

        # 設置滑鼠追蹤與事件
        self.videoWidget.setMouseTracking(True)
        self.videoWidget.installEventFilter(self)

        self.setupShortcuts()
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.playbackStateChanged.connect(self.updateButtons)
        self.loadAppIcon()

    def setupControls(self):
        self.controlsPanel = QWidget()
        self.controlsPanel.setFixedHeight(130)
        layout = QVBoxLayout(self.controlsPanel)
        layout.setContentsMargins(20, 10, 20, 15)
        
        # 進度條
        prog = QHBoxLayout()
        self.currTimeLbl = QLabel("00:00")
        self.totalTimeLbl = QLabel("00:00")
        self.slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider.sliderMoved.connect(self.setPosition)
        prog.addWidget(self.currTimeLbl)
        prog.addWidget(self.slider)
        prog.addWidget(self.totalTimeLbl)
        layout.addLayout(prog)

        # 按鈕列
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
        self.playBtn.setText("⏸" if state == QMediaPlayer.PlaybackState.PlayingState else "▶")

    def positionChanged(self, p):
        if not self.slider.isSliderDown(): self.slider.setValue(p)
        self.currTimeLbl.setText(self.formatTime(p))

    def durationChanged(self, d):
        self.slider.setRange(0, d); self.totalTimeLbl.setText(self.formatTime(d))

    def setPosition(self, p): self.mediaPlayer.setPosition(p)
    def seekRelative(self, ms): self.mediaPlayer.setPosition(max(0, min(self.mediaPlayer.position() + ms, self.mediaPlayer.duration())))
    def setVolume(self, v): self.audioOutput.setVolume(v / 100); self.volLbl.setText("🔊" if v > 0 else "🔇")
    
    def formatTime(self, ms):
        s, m, h = (ms // 1000) % 60, (ms // 60000) % 60, (ms // 3600000)
        return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"

    def toggleMiniPlayer(self):
        if not self.is_mini_mode:
            self.old_geometry = self.geometry()
            self.is_mini_mode = True
            self.controlsPanel.hide()
            self.leftSide.hide()
            self.rightSide.hide()
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
            self.resize(360, 202)
            self.show()
        else:
            self.exitSpecialModes()

    def toggleFullscreen(self):
        if self.isFullScreen():
            self.exitSpecialModes()
        else:
            self.old_geometry = self.geometry()
            self.controlsPanel.hide()
            self.leftSide.hide()
            self.rightSide.hide()
            self.showFullScreen()

    def exitSpecialModes(self):
        # 恢復視窗標誌與狀態
        self.is_mini_mode = False
        self.setWindowFlags(Qt.WindowType.Window)
        
        if self.isFullScreen():
            self.showNormal()
        
        self.controlsPanel.show()
        if len(self.playlist) > 1:
            self.leftSide.show()
            self.rightSide.show()
            
        if self.old_geometry:
            self.setGeometry(self.old_geometry)
        
        self.show()
        # 關鍵：有些系統需要額外的一步來確保邊框重繪
        QTimer.singleShot(50, self.showNormal)

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    if len(sys.argv) > 1: player.loadVideo(sys.argv[1])
    sys.exit(app.exec())
