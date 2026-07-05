import os
import subprocess
import re
from PyQt6.QtCore import QThread, pyqtSignal
from core.ffmpeg_utils import get_ffmpeg_exe, escape_path_for_ffmpeg

class ExportWorker(QThread):
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path, srt_path, audio_path, output_path, audio_mode, blur_mode, y_pct, h_pct, font_size):
        super().__init__()
        self.video_path = video_path
        self.srt_path = srt_path
        self.audio_path = audio_path
        self.output_path = output_path
        self.audio_mode = audio_mode
        self.blur_mode = blur_mode
        self.y_pct = y_pct
        self.h_pct = h_pct
        self.font_size = font_size
        self.is_running = True
        self.process = None

    def run(self):
        try:
            ffmpeg_exe = get_ffmpeg_exe()
            ffprobe_exe = ffmpeg_exe.replace("ffmpeg", "ffprobe")
            probe_cmd = [ffprobe_exe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", self.video_path]
            try:
                out = subprocess.check_output(probe_cmd, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0).strip()
                v_w, v_h = map(int, out.split('x'))
            except:
                v_w, v_h = 1920, 1080 
                
            block_y = int(v_h * self.y_pct)
            block_h = int(v_h * self.h_pct)
            block_y = block_y if block_y % 2 == 0 else block_y - 1
            block_h = block_h if block_h % 2 == 0 else block_h + 1
            if block_y < 0: block_y = 0
            
            cmd = [ffmpeg_exe, "-y", "-i", self.video_path]
            
            if self.audio_mode in ["Thay thế bằng lồng tiếng", "Mix (Gốc 10% + Lồng tiếng 100%)"] and self.audio_path:
                cmd.extend(["-i", self.audio_path])
                
            fc = []
            escaped_srt = escape_path_for_ffmpeg(self.srt_path)
            center_y = block_y + block_h / 2
            margin_v = v_h - int(center_y) - int(self.font_size / 1.5)
            if margin_v < 0: margin_v = 0
            vf_args = f"subtitles='{escaped_srt}':force_style='FontSize={self.font_size},Alignment=2,MarginV={margin_v}'"
            
            if self.blur_mode == "Làm mờ (Blur)":
                fc.append(f"[0:v]crop=iw:{block_h}:0:{block_y},boxblur=15[bg];[0:v][bg]overlay=0:{block_y}[vid];[vid]{vf_args}[out_v]")
            elif self.blur_mode == "Hộp đen (Black Box)":
                fc.append(f"[0:v]drawbox=x=0:y={block_y}:w=iw:h={block_h}:color=black@0.7:t=fill[vid];[vid]{vf_args}[out_v]")
            else:
                fc.append(f"[0:v]{vf_args}[out_v]")
                
            if self.audio_mode == "Mix (Gốc 10% + Lồng tiếng 100%)" and self.audio_path:
                fc.append("[0:a]volume=0.1[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=longest[out_a]")
                
            cmd.extend(["-filter_complex", ";".join(fc)])
            cmd.extend(["-map", "[out_v]"])
            
            if self.audio_mode == "Mix (Gốc 10% + Lồng tiếng 100%)" and self.audio_path:
                cmd.extend(["-map", "[out_a]"])
            elif self.audio_mode == "Thay thế bằng lồng tiếng" and self.audio_path:
                cmd.extend(["-map", "1:a:0"])
            else:
                cmd.extend(["-map", "0:a?"])
            
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            cmd.extend(["-shortest"])
            cmd.append(self.output_path)
            
            self.progress_updated.emit(5, "Đang chuẩn bị ghép cứng phụ đề...")
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo
            )
            
            duration_sec = 1.0
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            duration_pattern = re.compile(r"Duration: (\d+):(\d+):(\d+\.\d+)")
            
            for line in self.process.stdout:
                if not self.is_running:
                    self.process.kill()
                    return
                    
                dur_match = duration_pattern.search(line)
                if dur_match:
                    h, m, s = map(float, dur_match.groups())
                    duration_sec = h * 3600 + m * 60 + s
                    
                time_match = time_pattern.search(line)
                if time_match:
                    h, m, s = map(float, time_match.groups())
                    current_sec = h * 3600 + m * 60 + s
                    percent = min(99, int((current_sec / max(1.0, duration_sec)) * 100))
                    self.progress_updated.emit(percent, f"Đang render: {int(current_sec)}s / {int(duration_sec)}s...")
            
            self.process.wait()
            
            if self.process.returncode == 0:
                self.progress_updated.emit(100, "Xuất video hoàn tất thành công!")
                self.finished.emit(self.output_path)
            else:
                if self.is_running:
                    self.error_occurred.emit("FFmpeg gặp lỗi trong quá trình render video.")
                
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.kill()
            except:
                pass
