
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, QTimer

def test_playback(file_path):
    app = QApplication(sys.argv)
    player = QMediaPlayer()
    audio = QAudioOutput()
    player.setAudioOutput(audio)
    
    def handle_error():
        print(f"ERROR: {player.error()} - {player.errorString()}")
        app.quit()
        
    def handle_status(status):
        print(f"STATUS: {status}")
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            print("Media loaded successfully!")
            print(f"Duration: {player.duration()}")
            app.quit()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            print("Media is INVALID.")
            app.quit()

    player.errorOccurred.connect(handle_error)
    player.mediaStatusChanged.connect(handle_status)
    
    abs_path = os.path.abspath(file_path)
    print(f"Testing file: {abs_path}")
    if not os.path.exists(abs_path):
        print("File does not exist!")
        return

    url = QUrl.fromLocalFile(abs_path)
    player.setSource(url)
    player.play()
    
    # Timeout after 5 seconds
    QTimer.singleShot(5000, app.quit)
    app.exec()

if __name__ == "__main__":
    test_path = r"E:\社會經濟學\chaturbate\angela_5\Angelaagh_2020_02_08 - CamWhores.mp4"
    test_playback(test_path)
