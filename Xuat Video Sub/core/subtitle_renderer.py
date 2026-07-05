import os
try:
    import pysrt
except ImportError:
    pysrt = None

class SubtitleRenderer:
    def __init__(self):
        self.subs = []

    def load_srt(self, filepath: str) -> bool:
        """Load SRT file, testing multiple encodings for robustness."""
        if pysrt is None:
            return False
            
        if not os.path.exists(filepath):
            self.subs = []
            return False

        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1', 'cp1252', 'gbk']
        for enc in encodings:
            try:
                self.subs = pysrt.open(filepath, encoding=enc)
                return True
            except Exception:
                continue
                
        # Fallback to default loading if all fails
        try:
            self.subs = pysrt.open(filepath)
            return True
        except Exception:
            self.subs = []
            return False

    def get_subtitle_at_time(self, current_time_ms: int) -> str:
        """Get the subtitle text to display at the given time."""
        if not self.subs:
            return ""

        # Using pysrt's slice method based on time. 
        # slice(starts_before, ends_after)
        # Note: pysrt slice(starts_before={'milliseconds': current_time_ms}, ends_after={'milliseconds': current_time_ms})
        # Alternatively, we can just iterate. Since there aren't thousands of active at once, a binary search or linear search is fine.
        # But wait, subs.slice is clean but can be slow if called every frame.
        # Linear search with caching or just simple iteration since it's 1-2 subs usually.
        
        # Simple iteration is O(N) but N is usually small.
        # To optimize, we can use binary search or just linear search.
        
        active_texts = []
        for sub in self.subs:
            start_ms = sub.start.ordinal
            end_ms = sub.end.ordinal
            
            if start_ms <= current_time_ms <= end_ms:
                active_texts.append(sub.text)
            elif start_ms > current_time_ms:
                # Since SRT is sorted by start time, we can break early
                break
                
        return "\n".join(active_texts)
