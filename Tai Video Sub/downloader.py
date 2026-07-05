import os
import yt_dlp
from PyQt6.QtCore import QThread, pyqtSignal

class DownloadWorker(QThread):
    progress = pyqtSignal(dict)
    finished = pyqtSignal(str, bool, str) # title, success, error_message

    def __init__(self, url, output_dir, browser=None):
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.browser = browser
        self._is_cancelled = False

    def run(self):
        def progress_hook(d):
            if self._is_cancelled:
                raise Exception("Đã hủy quá trình tải.")
            self.progress.emit(d)

        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'format': 'bestvideo+bestaudio/best',
            'noplaylist': True,
            'writethumbnail': True,
            'postprocessors': [{'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}]
        }
        
        if self.browser:
            ydl_opts['cookiesfrombrowser'] = (self.browser, )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                title = info.get('title', 'Video')
                self.finished.emit(title, True, "")
        except Exception as e:
            self.finished.emit("", False, str(e))

    def cancel(self):
        self._is_cancelled = True
