import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSlider, QFileDialog, QLabel)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, QTime, QPoint, QSize, QTimer, QRect
from PyQt6.QtGui import QShortcut, QKeySequence, QMouseEvent, QWindow, QCursor

class ClickableSlider(QSlider):
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)

class MiniControlOverlay(QWidget):
    def __init__(self, parent_player):
        super().__init__(None)
        self.player = parent_player
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.restoreBtn = QPushButton("🗗")
        self.closeBtn = QPushButton("✕")
        
        for btn in [self.restoreBtn, self.closeBtn]:
            btn.setFixedSize(30, 30)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet("""
                QPushButton { 
                    background-color: rgba(40, 40, 40, 220); color: white; border-radius: 15px; font-weight: bold; border: 1px solid rgba(255,255,255,40);
                }
                QPushButton:hover { background-color: rgba(80, 80, 80, 255); }
            """)
        
        self.closeBtn.setStyleSheet(self.closeBtn.styleSheet() + "QPushButton { background-color: rgba(200, 0, 0, 220); }")
        self.restoreBtn.clicked.connect(self.player.exitSpecialModes)
        self.closeBtn.clicked.connect(self.player.close)
        
        layout.addWidget(self.restoreBtn)
        layout.addWidget(self.closeBtn)

    def syncPosition(self):
        if self.player.isVisible():
            player_screen = self.player.screen()
            if self.screen() != player_screen:
                self.setScreen(player_screen)
            geom = self.player.geometry()
            self.move(geom.right() - 75, geom.top() + 10)

class ClickableVideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None
        self.press_pos = QPoint()
        self.setMouseTracking(True)

    def set_main_window(self, win):
        self.main_window = win

    def mousePressEvent(self, event):
        if self.main_window and self.main_window.is_mini_mode:
            pos = self.mapToParent(event.position().toPoint())
            if self.main_window.get_resize_direction(pos):
                event.ignore()
                return
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.main_window:
            self.main_window.handleMouseRelease(event)
        if event.button() == Qt.MouseButton.LeftButton:
            distance = (event.globalPosition().toPoint() - self.press_pos).manhattanLength()
            if distance < 5: 
                if self.main_window: self.main_window.playVideo()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.main_window:
            self.main_window.handleMouseMove(event)
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        if self.main_window and (self.main_window.is_mini_mode or self.main_window.isFullScreen()):
            self.main_window.overlay.syncPosition()
            self.main_window.overlay.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        QTimer.singleShot(100, self.check_leave)
        super().leaveEvent(event)

    def check_leave(self):
        if self.main_window and not self.main_window.overlay.underMouse() and not self.underMouse():
            self.main_window.overlay.hide()

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Gemini Pro Player")
        self.resize(1100, 750)
        self.is_mini_mode = False
        self.old_geometry = None
        self.drag_pos = QPoint()
        self.edge_margin = 10
        self.resize_direction = None

        self.mediaPlayer = QMediaPlayer()
        self.videoWidget = ClickableVideoWidget()
        self.videoWidget.set_main_window(self)
        self.audioOutput = QAudioOutput()
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.setAudioOutput(self.audioOutput)

        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QVBoxLayout(self.centralWidget)
        self.mainLayout.setContentsMargins(0, 0, 0, 0)
        self.mainLayout.setSpacing(0)
        self.mainLayout.addWidget(self.videoWidget)
        self.centralWidget.setMouseTracking(True)
        self.setMouseTracking(True)

        self.overlay = MiniControlOverlay(self)

        self.controlsPanel = QWidget()
        self.controlsPanel.setFixedHeight(130)
        self.controlsPanel.setObjectName("controlsPanel")
        self.panelLayout = QVBoxLayout(self.controlsPanel)
        self.panelLayout.setContentsMargins(20, 10, 20, 15)
        
        # 進度條區域
        progressLayout = QHBoxLayout()
        self.currentTimeLabel = QLabel("00:00")
        self.totalTimeLabel = QLabel("00:00")
        self.currentTimeLabel.setFixedWidth(50)
        self.totalTimeLabel.setFixedWidth(50)
        self.currentTimeLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.positionSlider = ClickableSlider(Qt.Orientation.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.setPosition)
        self.positionSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.positionSlider.setCursor(Qt.CursorShape.PointingHandCursor)
        
        progressLayout.addWidget(self.currentTimeLabel)
        progressLayout.addWidget(self.positionSlider)
        progressLayout.addWidget(self.totalTimeLabel)
        self.panelLayout.addLayout(progressLayout)

        # 按鈕控制區域
        btnsLayout = QHBoxLayout()
        btnsLayout.setSpacing(15)
        
        # 左側功能
        self.openBtn = self.createIconButton("📂 開啟檔案", self.openFile)
        self.openBtn.setFixedWidth(110)
        self.openBtn.setStyleSheet("background-color: #333333; font-size: 13px; color: #EEEEEE;")
        
        # 中間播放控制 (居中關鍵)
        self.backBtn = self.createIconButton("⏪", lambda: self.seekRelative(-5000))
        self.playBtn = self.createIconButton("▶", self.playVideo)
        self.forwardBtn = self.createIconButton("⏩", lambda: self.seekRelative(5000))
        
        self.backBtn.setFixedSize(45, 45)
        self.playBtn.setFixedSize(55, 55)
        self.forwardBtn.setFixedSize(45, 45)
        
        self.playBtn.setObjectName("playBtn")
        self.playBtn.setStyleSheet("""
            QPushButton#playBtn { 
                background-color: #00ADB5; 
                color: white; 
                font-size: 24px; 
                border-radius: 27px; 
            }
            QPushButton#playBtn:hover { background-color: #00FFF5; }
        """)

        # 右側功能與音量
        self.miniBtn = self.createIconButton("📺 小窗模式", self.toggleMiniPlayer)
        self.miniBtn.setFixedWidth(110)
        self.miniBtn.setStyleSheet("background-color: #333333; font-size: 13px; color: #EEEEEE;")
        
        volumeLayout = QHBoxLayout()
        self.volLabel = QLabel("🔊")
        self.volumeSlider = QSlider(Qt.Orientation.Horizontal)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setValue(70)
        self.audioOutput.setVolume(0.7)
        self.volumeSlider.setFixedWidth(100)
        self.volumeSlider.valueChanged.connect(self.setVolume)
        self.volumeSlider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.volumeSlider.setCursor(Qt.CursorShape.PointingHandCursor)
        volumeLayout.addWidget(self.volLabel)
        volumeLayout.addWidget(self.volumeSlider)

        # 組合佈局：[開啟] -- [Stretch] -- [回退][播放][快進] -- [Stretch] -- [小窗][音量]
        btnsLayout.addWidget(self.openBtn)
        btnsLayout.addStretch(1) 
        
        btnsLayout.addWidget(self.backBtn)
        btnsLayout.addWidget(self.playBtn)
        btnsLayout.addWidget(self.forwardBtn)
        
        btnsLayout.addStretch(1)
        
        btnsLayout.addWidget(self.miniBtn)
        btnsLayout.addSpacing(10)
        btnsLayout.addLayout(volumeLayout)
        
        self.panelLayout.addLayout(btnsLayout)
        self.mainLayout.addWidget(self.controlsPanel)

        self.applyModernStyle()

        # 快捷鍵
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.playVideo)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.seekRelative(-5000))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.seekRelative(5000))
        QShortcut(QKeySequence(Qt.Key.Key_F), self, self.toggleFullscreen)
        QShortcut(QKeySequence(Qt.Key.Key_P), self, self.toggleMiniPlayer)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.exitSpecialModes)

        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.playbackStateChanged.connect(self.updateButtons)
        self.mediaPlayer.errorOccurred.connect(self.handleError)
        self.mediaPlayer.mediaStatusChanged.connect(self.handleMediaStatus)

    def handleMediaStatus(self, status):
        print(f"Media Status changed to: {status}")
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            print(f"Media loaded. Has video: {self.mediaPlayer.hasVideo()}, Has audio: {self.mediaPlayer.hasAudio()}")
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            print("Media is invalid.")

    def handleError(self):
        err = self.mediaPlayer.error()
        err_str = self.mediaPlayer.errorString()
        print(f"Error occurred: {err} - {err_str}")
        if err != QMediaPlayer.Error.NoError:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "播放錯誤", f"無法播放此檔案。\n錯誤訊息: {err_str}\n\n這通常是因為缺少對應的解碼器 (Codec)，建議安裝 K-Lite Codec Pack。")

    def showEvent(self, event):
        super().showEvent(event)
        handle = self.windowHandle()
        if handle:
            handle.screenChanged.connect(lambda: self.overlay.syncPosition())

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

    def createIconButton(self, text, slot):
        btn = QPushButton(text)
        btn.clicked.connect(slot)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def get_resize_direction(self, pos):
        if not self.is_mini_mode: return None
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        dir = ""
        if y < self.edge_margin: dir += "T"
        elif y > h - self.edge_margin: dir += "B"
        if x < self.edge_margin: dir += "L"
        elif x > w - self.edge_margin: dir += "R"
        return dir if dir else None

    def update_cursor(self, dir):
        if dir in ["TL", "BR"]: self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif dir in ["TR", "BL"]: self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif dir in ["T", "B"]: self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif dir in ["L", "R"]: self.setCursor(Qt.CursorShape.SizeHorCursor)
        else: self.setCursor(Qt.CursorShape.ArrowCursor)

    def handleMouseMove(self, event):
        pos = self.mapFromGlobal(event.globalPosition().toPoint())
        self.processMouseMove(pos, event.globalPosition().toPoint(), event.buttons())

    def handleMouseRelease(self, event):
        self.resize_direction = None
        self.update_cursor(None)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self.processMouseMove(pos, event.globalPosition().toPoint(), event.buttons())
        super().mouseMoveEvent(event)

    def processMouseMove(self, local_pos, global_pos, buttons):
        if buttons == Qt.MouseButton.NoButton:
            dir = self.get_resize_direction(local_pos)
            self.update_cursor(dir)
        elif buttons == Qt.MouseButton.LeftButton:
            if self.resize_direction:
                rect = QRect(self.drag_geometry)
                diff = global_pos - self.drag_pos
                if 'L' in self.resize_direction: rect.setLeft(rect.left() + diff.x())
                if 'R' in self.resize_direction: rect.setRight(rect.right() + diff.x())
                if 'T' in self.resize_direction: rect.setTop(rect.top() + diff.y())
                if 'B' in self.resize_direction: rect.setBottom(rect.bottom() + diff.y())
                if rect.width() > 150 and rect.height() > 100:
                    self.setGeometry(rect)
            else:
                self.move(global_pos - self.drag_pos)
            self.overlay.syncPosition()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.resize_direction = self.get_resize_direction(pos)
            if self.resize_direction:
                self.drag_pos = event.globalPosition().toPoint()
                self.drag_geometry = self.geometry()
            else:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.handleMouseRelease(event)
        super().mouseReleaseEvent(event)

    def toggleMiniPlayer(self):
        if not self.is_mini_mode:
            self.old_geometry = self.geometry()
            self.is_mini_mode = True
            self.controlsPanel.hide()
            ratio = self.screen().logicalDotsPerInch() / 96.0
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
            self.resize(int(360 * ratio), int(202 * ratio))
            self.show()
            QTimer.singleShot(50, self.overlay.syncPosition)
        else:
            self.exitSpecialModes()

    def exitSpecialModes(self):
        self.is_mini_mode = False
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.controlsPanel.show()
        if self.old_geometry: self.setGeometry(self.old_geometry)
        else: self.resize(1100, 750)
        self.show()
        self.overlay.hide()

    def toggleFullscreen(self):
        if self.isFullScreen(): self.exitSpecialModes()
        else:
            self.old_geometry = self.geometry()
            self.showFullScreen()
            self.controlsPanel.hide()
            QTimer.singleShot(50, self.overlay.syncPosition)

    def closeEvent(self, event):
        self.overlay.close()
        super().closeEvent(event)

    def setVolume(self, volume):
        self.audioOutput.setVolume(volume / 100)
        self.volLabel.setText("🔊" if volume > 0 else "🔇")

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "選取影片", "", "Videos (*.mp4 *.mkv *.avi *.mov *.wmv)")
        self.loadVideo(fileName)

    def loadVideo(self, fileName):
        if fileName:
            # 處理 Windows 傳入路徑可能帶有的引號或反斜槓
            fileName = fileName.replace('"', '').replace('\\', '/')
            print(f"Loading file: {fileName}")
            
            self.mediaPlayer.stop()
            file_url = QUrl.fromLocalFile(fileName)
            if file_url.isValid():
                self.mediaPlayer.setSource(file_url)
                self.mediaPlayer.play()
                # 更新標題顯示檔名
                base_name = fileName.split('/')[-1]
                self.setWindowTitle(f"Gemini Pro Player - {base_name}")
            else:
                print("Error: Invalid URL from file path")

    def playVideo(self):
        state = self.mediaPlayer.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState: self.mediaPlayer.pause()
        else: self.mediaPlayer.play()

    def updateButtons(self, state):
        self.playBtn.setText("⏸" if state == QMediaPlayer.PlaybackState.PlayingState else "▶")

    def positionChanged(self, position):
        if not self.positionSlider.isSliderDown(): self.positionSlider.setValue(position)
        self.currentTimeLabel.setText(self.formatTime(position))

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)
        self.totalTimeLabel.setText(self.formatTime(duration))

    def setPosition(self, position): self.mediaPlayer.setPosition(position)

    def seekRelative(self, ms):
        newPos = self.mediaPlayer.position() + ms
        self.mediaPlayer.setPosition(max(0, min(newPos, self.mediaPlayer.duration())))

    def formatTime(self, ms):
        s = (ms // 1000) % 60
        m = (ms // 60000) % 60
        h = (ms // 3600000)
        return f"{h:02}:{m:02}:{s:02}" if h > 0 else f"{m:02}:{s:02}"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    
    # 檢查是否有傳入檔案路徑參數
    if len(sys.argv) > 1:
        # Windows 傳遞檔案路徑作為第一個參數
        video_path = sys.argv[1]
        player.loadVideo(video_path)
        
    sys.exit(app.exec())
