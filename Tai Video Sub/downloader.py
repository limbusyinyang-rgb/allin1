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

        try:
            import imageio_ffmpeg
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_path = "ffmpeg" # Fallback

        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, '%(title)s', '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'writethumbnail': True,
            'postprocessors': [{'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}],
            'ffmpeg_location': ffmpeg_path
        }
        
        if self.browser:
            ydl_opts['cookiesfrombrowser'] = (self.browser, )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                title = info.get('title', 'Video')
                self.finished.emit(title, True, "")
        except Exception as e:
            error_msg = str(e)
            if "Failed to decrypt with DPAPI" in error_msg:
                error_msg = "Lỗi khóa bảo mật trình duyệt Chrome/Edge!\\n=> Vui lòng TẮT HẲN trình duyệt rồi bấm tải lại.\\n=> Hoặc BỎ CHỌN mục 'Lấy Cookie' nếu không cần thiết."
            self.finished.emit("", False, error_msg)

    def cancel(self):
        self._is_cancelled = True
