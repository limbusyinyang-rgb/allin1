import os
import re
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

class FFmpegExportEngine(QThread):
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    finished = pyqtSignal(str, bool)  # output_path, success

    def __init__(self, config_dict):
        super().__init__()
        self.config = config_dict
        self.is_running = True
        self.process = None

    def find_ffmpeg(self):
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
            
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return "ffmpeg"
        except Exception:
            return None

    def run(self):
        ffmpeg_exe = self.find_ffmpeg()
        if not ffmpeg_exe:
            self.log_updated.emit("ERROR: Không tìm thấy FFmpeg.")
            self.finished.emit("", False)
            return

        video_path = self.config.get("video_input", "")
        output_path = self.config.get("output_input", "")
        if not video_path or not output_path:
            self.log_updated.emit("ERROR: Thiếu đường dẫn file.")
            self.finished.emit("", False)
            return
            
        # Get video info (duration, resolution)
        duration = 100.0
        width = 1920
        height = 1080
        try:
            probe = subprocess.run([ffmpeg_exe, "-i", video_path], stderr=subprocess.PIPE, text=True, encoding="utf-8")
            match_dur = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
            if match_dur:
                h, m, s = match_dur.groups()
                duration = int(h) * 3600 + int(m) * 60 + float(s)
            match_res = re.search(r"Video:.* (\d{3,4})x(\d{3,4})", probe.stderr)
            if match_res:
                width = int(match_res.group(1))
                height = int(match_res.group(2))
            has_audio = "Audio:" in probe.stderr
        except Exception as e:
            self.log_updated.emit(f"Warning: Không thể probe video - {e}")
            has_audio = True # Fallback assume it has audio
            
        cmd = [ffmpeg_exe, "-y", "-i", video_path]
        filter_complex = []
        inputs_count = 1  # [0:v] and [0:a]
        
        # Audio Mixing
        orig_vol = self.config.get("orig_audio_vol", 1.0)
        added_audio = self.config.get("added_audio", "")
        added_vol = self.config.get("added_audio_vol", 1.0)
        trim_video = self.config.get("trim_video", True)
        
        has_added_audio = bool(added_audio and os.path.exists(added_audio))
        
        if has_audio and orig_vol > 0:
            audio_filter = f"[0:a]volume={orig_vol}[a0];"
            if has_added_audio:
                cmd.extend(["-i", added_audio])
                # If trim is enabled, amix duration is shortest (which is the shortest of original or added)
                # Or we just use longest and let -shortest global flag handle the trim
                a1_flt = f"[{inputs_count}:a]volume={added_vol}[a1];"
                audio_filter += a1_flt
                amix_dur = "shortest" if trim_video else "longest"
                audio_filter += f"[a0][a1]amix=inputs=2:duration={amix_dur}[aout]"
                inputs_count += 1
            else:
                audio_filter += "[a0]acopy[aout]"
        else:
            # Original audio muted or not present
            if has_added_audio:
                cmd.extend(["-i", added_audio])
                audio_filter = f"[{inputs_count}:a]volume={added_vol}[aout]"
                inputs_count += 1
            else:
                # No audio at all, we must provide a dummy silent audio or just not map [aout]
                audio_filter = f"anullsrc=r=44100:cl=stereo[aout]"
                
        # Handle global trim flag
        if trim_video and has_added_audio:
            cmd.append("-shortest")
            
        # Video Filter Complex
        # 1. Start with [0:v]
        current_v = "[0:v]"
        v_filters = []
        
        # 2. Blurs
        blurs = self.config.get("blurs", []).copy()
        
        # Auto inject background blur for subtitles if enabled
        sub_style = self.config.get("sub_style", None)
        if sub_style and getattr(sub_style, "use_background_blur", False):
            class SubBlur:
                intensity = sub_style.blur_intensity
                x_pct = sub_style.box_x_pct + (sub_style.box_w_pct / 2.0)
                w_pct = sub_style.box_w_pct
                y_pct = sub_style.box_y_pct + (sub_style.box_h_pct / 2.0)
                h_pct = sub_style.box_h_pct
            blurs.append(SubBlur())
            
        watermarks = self.config.get("watermarks", [])
        for wm in watermarks:
            if getattr(wm, "use_background_blur", False):
                class WmBlur:
                    intensity = wm.blur_intensity
                    x_pct = wm.x_pct
                    w_pct = wm.w_pct
                    y_pct = wm.y_pct
                    h_pct = wm.h_pct
                blurs.append(WmBlur())
            
        for i, b in enumerate(blurs):
            bx = int(b.x_pct * width - (b.w_pct * width / 2))
            by = int(b.y_pct * height - (b.h_pct * height / 2))
            bw = int(b.w_pct * width)
            bh = int(b.h_pct * height)
            
            bx = max(0, bx)
            by = max(0, by)
            bw = min(width - bx, bw)
            bh = min(height - by, bh)
            
            if b.intensity > 0:
                # Use gblur matching OpenCV logic exactly
                kernel = 1 + int(b.intensity * 2)
                if kernel % 2 == 0: kernel += 1
                sigma = kernel / 3.0
                
                b_flt = f"gblur=sigma={sigma}"
                
                radius_pct = getattr(b, "corner_radius", 0)
                if radius_pct > 0:
                    import tempfile
                    import uuid
                    from PyQt6.QtGui import QImage, QPainter, QColor, QPainterPath
                    from PyQt6.QtCore import Qt, QRectF
                    
                    radius = min(bw, bh) / 2.0 * (radius_pct / 100.0)
                    mask_path = os.path.join(tempfile.gettempdir(), f"blur_mask_{uuid.uuid4().hex}.png")
                    
                    # Create White on Black mask image
                    img = QImage(bw, bh, QImage.Format.Format_RGB32)
                    img.fill(QColor(0, 0, 0)) # Black
                    painter = QPainter(img)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setBrush(QColor(255, 255, 255)) # White
                    painter.setPen(Qt.PenStyle.NoPen)
                    path = QPainterPath()
                    path.addRoundedRect(QRectF(0, 0, bw, bh), radius, radius)
                    painter.drawPath(path)
                    painter.end()
                    img.save(mask_path, "PNG")
                    
                    # Add mask as input
                    cmd.extend(["-i", mask_path])
                    mask_idx = inputs_count
                    inputs_count += 1
                    
                    v_filters.append(f"{current_v}crop={bw}:{bh}:{bx}:{by},{b_flt}[blur_crop{i}]")
                    # alphamerge uses grayscale value of second input as alpha
                    v_filters.append(f"[blur_crop{i}][{mask_idx}:v]alphamerge[blur_masked{i}]")
                    v_filters.append(f"{current_v}[blur_masked{i}]overlay=x={bx}:y={by}[v_after_blur{i}]")
                else:
                    v_filters.append(f"{current_v}crop={bw}:{bh}:{bx}:{by},{b_flt}[blur{i}]")
                    v_filters.append(f"{current_v}[blur{i}]overlay=x={bx}:y={by}[v_after_blur{i}]")
                
                current_v = f"[v_after_blur{i}]"
            
        # 3. Watermarks
        watermarks = self.config.get("watermarks", [])
        for i, w in enumerate(watermarks):
            wx = int(w.x_pct * width - (w.w_pct * width / 2))
            wy = int(w.y_pct * height - (w.h_pct * height / 2))
            if w.is_text:
                # Use drawtext
                color = w.color.replace('#', '0x') if w.use_color else "0xFFFFFF"
                escaped_text = w.text.replace("'", "\\'").replace(":", "\\:")
                dt_str = f"drawtext=text='{escaped_text}':x={wx}:y={wy}:fontsize={w.font_size}:fontcolor={color}@{w.opacity}"
                if w.use_outline:
                    dt_str += f":borderw={w.outline_width}:bordercolor={w.outline_color.replace('#', '0x')}@{w.opacity}"
                if w.use_glow:
                    dt_str += f":shadowx={w.glow_radius}:shadowy={w.glow_radius}:shadowcolor={w.glow_color.replace('#', '0x')}@{w.opacity}"
                    
                v_filters.append(f"{current_v}{dt_str}[v_after_wm{i}]")
                current_v = f"[v_after_wm{i}]"
            else:
                if w.image_path and os.path.exists(w.image_path):
                    cmd.extend(["-i", w.image_path])
                    ww = int(w.w_pct * width)
                    wh = int(w.h_pct * height)
                    v_filters.append(f"[{inputs_count}:v]scale={ww}:{wh},colorchannelmixer=aa={w.opacity}[wm_img{i}]")
                    v_filters.append(f"{current_v}[wm_img{i}]overlay=x={wx}:y={wy}[v_after_wm{i}]")
                    current_v = f"[v_after_wm{i}]"
                    inputs_count += 1
                    
        # 4. Subtitles
        srt_path = self.config.get("srt_input", "")
        sub_style = self.config.get("sub_style", None)
        if srt_path and os.path.exists(srt_path) and sub_style:
            # Escape path for FFmpeg
            escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")
            # Use ASS styling via force_style
            # alignment 2 = bottom center. We also need to factor in box_y_pct for margin_v
            margin_v = int(height - (sub_style.box_y_pct * height + (sub_style.box_h_pct * height / 2)))
            margin_v = max(0, margin_v)
            
            def hex_to_ass(h):
                h = h.lstrip('#')
                return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}"
                
            c_primary = hex_to_ass(sub_style.color) if sub_style.use_color else "&H00FFFFFF"
            c_outline = hex_to_ass(sub_style.outline_color) if sub_style.use_outline else "&H00000000"
            c_shadow = hex_to_ass(sub_style.glow_color) if sub_style.use_glow else "&H00000000"
            
            outline_val = sub_style.outline_width if sub_style.use_outline else 0
            shadow_val = sub_style.glow_radius if sub_style.use_glow else 0
            
            f_style = f"FontSize={sub_style.font_size},MarginV={margin_v},Alignment=2,PrimaryColour={c_primary},OutlineColour={c_outline},BackColour={c_shadow},Outline={outline_val},Shadow={shadow_val},BorderStyle=1"
            v_filters.append(f"{current_v}subtitles='{escaped_srt}':force_style='{f_style}'[vout]")
        else:
            v_filters.append(f"{current_v}copy[vout]")

        # Combine filter_complex
        fc_str = audio_filter + ";" + ";".join(v_filters)
        cmd.extend(["-filter_complex", fc_str, "-map", "[vout]", "-map", "[aout]"])
        
        # Export Settings
        codec = self.config.get("codec", "libx264")
        if codec == "H264 (NVENC)": codec_v = "h264_nvenc"
        elif codec == "H264 (QuickSync)": codec_v = "h264_qsv"
        else: codec_v = "libx264"
        
        cmd.extend(["-c:v", codec_v])
        
        bitrate = self.config.get("bitrate", "Auto")
        if bitrate != "Auto":
            cmd.extend(["-b:v", f"{bitrate}M"])
            
        cmd.extend(["-c:a", "aac", "-b:a", self.config.get("audio_bitrate", "192k")])
        cmd.append(output_path)
        
        self.log_updated.emit(f"Running command: {' '.join(cmd)}")
        
        # Execute
        try:
            # CREATE_NO_WINDOW = 0x08000000
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", creationflags=0x08000000)
            
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            for line in self.process.stdout:
                if not self.is_running:
                    self.process.kill()
                    self.log_updated.emit("Đã hủy quá trình xuất video.")
                    self.finished.emit("", False)
                    return
                
                self.log_updated.emit(line.strip())
                match = time_pattern.search(line)
                if match and duration > 0:
                    h, m, s = match.groups()
                    current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    pct = int((current_sec / duration) * 100)
                    self.progress_updated.emit(min(100, pct))
            
            self.process.wait()
            if self.process.returncode == 0:
                self.progress_updated.emit(100)
                self.log_updated.emit("Xuất video thành công!")
                self.finished.emit(output_path, True)
            else:
                self.log_updated.emit(f"FFmpeg exit code: {self.process.returncode}")
                self.finished.emit("", False)
                
        except Exception as e:
            self.log_updated.emit(f"Exception: {str(e)}")
            self.finished.emit("", False)

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.kill()
            except:
                pass
