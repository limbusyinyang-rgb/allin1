import os
import pysrt

def parse_srt(srt_file):
    subs_list = []
    if not os.path.exists(srt_file):
        return subs_list
        
    try:
        subs = pysrt.open(srt_file, encoding='utf-8')
        for sub in subs:
            start_ms = (sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds) * 1000 + sub.start.milliseconds
            end_ms = (sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds) * 1000 + sub.end.milliseconds
            subs_list.append({'start': start_ms, 'end': end_ms, 'text': sub.text})
    except Exception as e:
        print("Error parsing SRT with pysrt:", e)
                
    return subs_list
