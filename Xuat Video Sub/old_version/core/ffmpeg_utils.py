def get_ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        print(f"Warning: {e}")
        return "ffmpeg"

def escape_path_for_ffmpeg(path):
    path = path.replace("\\", "/")
    path = path.replace(":", "\\:")
    return path
