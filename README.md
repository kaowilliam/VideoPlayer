# Gemini Pro Player 🎬

這是一款基於 **Python 3** 與 **PyQt6** 開發的現代化影片播放器。它具備極簡、現代的 UI 設計，並針對桌面端的使用體驗進行了深度優化。

## ✨ 特色功能
- **現代化 UI**：採用深色模式 (Dark Mode) 與青綠色系主題，控制面板居中且易於操作。
- **小窗模式 (PiP)**：支援置頂小窗播放，並可隨意拖動位置與調整視窗大小。
- **全螢幕切換**：支援 `F` 鍵快速進入/退出全螢幕。
- **智慧進度控制**：支援 5 秒快轉/倒退，並提供點擊式進度條。
- **系統整合**：支援透過 Windows 命令列或「開啟方式」直接啟動並播放特定影片。
- **獨立執行檔**：已透過 PyInstaller 打包，無需安裝 Python 環境即可運行。

## 🛠 技術細節
- **核心框架**：`PyQt6` (Qt 6.x)
- **多媒體引擎**：`QtMultimedia` & `FFmpeg` (內建於 Qt 6)
- **佈局管理**：採用對稱式 `QHBoxLayout` 與 `QVBoxLayout` 實現響應式介面。
- **事件處理**：自定義 `ClickableVideoWidget` 以處理複雜的滑鼠拖拽與縮放邏輯。
- **打包工具**：`PyInstaller` (--onefile --noconsole)

## 📦 安裝與環境
若要自行編譯，請安裝以下套件：
```bash
pip install PyQt6
```

### 關於編碼器 (Codec)
本播放器依賴系統解碼器。若遇到無法播放的格式（如部分 H.265/HEVC 影片），建議安裝：
- [K-Lite Codec Pack (Full)](https://codecguide.com/download_k-lite_codec_pack_full.htm)
安裝後即可支援市面上 99% 的影片格式。

## ⌨️ 快捷鍵說明
- `Space`：播放 / 暫停
- `Left` / `Right`：倒退 / 快進 5 秒
- `F`：切換全螢幕
- `P`：切換小窗模式
- `Esc`：退出特殊模式（全螢幕或小窗）

---
*Developed with ❤️ by Gemini CLI*
