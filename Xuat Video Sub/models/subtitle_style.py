from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SubtitleStyle:
    font_family: str = "Arial"
    font_size: float = 48.0
    use_color: bool = True
    color: str = "#FFFFFF"       # Hex color
    use_outline: bool = False
    outline_color: str = "#000000"
    outline_width: float = 2.0
    use_glow: bool = False
    glow_color: str = "#000000"
    glow_radius: float = 2.0
    alignment: int = 2           # ASS alignment (2 = Bottom Center)
    margin_v: int = 10           # Vertical margin
    opacity: float = 1.0         # 0.0 to 1.0
    line_spacing: int = 0
    # Relative coordinates (0.0 - 1.0) for the subtitle box area
    box_x_pct: float = 0.1
    box_y_pct: float = 0.8
    box_w_pct: float = 0.8
    box_h_pct: float = 0.15
    use_background_blur: bool = False
    blur_intensity: int = 30
    
    def save(self):
        from PyQt6.QtCore import QSettings
        settings = QSettings("MyCapCut", "SubtitleStyle")
        settings.setValue("font_family", self.font_family)
        settings.setValue("font_size", self.font_size)
        settings.setValue("use_color", self.use_color)
        settings.setValue("color", self.color)
        settings.setValue("use_outline", self.use_outline)
        settings.setValue("outline_color", self.outline_color)
        settings.setValue("outline_width", self.outline_width)
        settings.setValue("use_glow", self.use_glow)
        settings.setValue("glow_color", self.glow_color)
        settings.setValue("glow_radius", self.glow_radius)
        settings.setValue("box_x_pct", self.box_x_pct)
        settings.setValue("box_y_pct", self.box_y_pct)
        settings.setValue("box_w_pct", self.box_w_pct)
        settings.setValue("box_h_pct", self.box_h_pct)
        
    @classmethod
    def load(cls):
        from PyQt6.QtCore import QSettings
        settings = QSettings("MyCapCut", "SubtitleStyle")
        
        def get_bool(key, default):
            v = settings.value(key, default)
            return str(v).lower() == 'true' if isinstance(v, str) else bool(v)
            
        def get_float(key, default):
            try: return float(settings.value(key, default))
            except: return default
            
        return cls(
            font_family=str(settings.value("font_family", "Arial")),
            font_size=get_float("font_size", 48.0),
            use_color=get_bool("use_color", True),
            color=str(settings.value("color", "#FFFFFF")),
            use_outline=get_bool("use_outline", False),
            outline_color=str(settings.value("outline_color", "#000000")),
            outline_width=get_float("outline_width", 2.0),
            use_glow=get_bool("use_glow", False),
            glow_color=str(settings.value("glow_color", "#000000")),
            glow_radius=get_float("glow_radius", 2.0),
            box_x_pct=get_float("box_x_pct", 0.1),
            box_y_pct=get_float("box_y_pct", 0.8),
            box_w_pct=get_float("box_w_pct", 0.8),
            box_h_pct=get_float("box_h_pct", 0.15)
        )

@dataclass
class WatermarkModel:
    id: str
    is_text: bool = True
    # For Text
    text: str = ""
    font_family: str = "Arial"
    font_size: float = 24.0
    use_color: bool = True
    color: str = "#FFFFFF"
    use_outline: bool = False
    outline_color: str = "#000000"
    outline_width: float = 2.0
    use_glow: bool = False
    glow_color: str = "#000000"
    glow_radius: float = 2.0
    # For Image
    image_path: str = ""
    # Common properties
    opacity: float = 1.0         # 0.0 to 1.0
    rotation: float = 0.0        # Degrees
    # Relative coordinates (0.0 - 1.0) for bounding box center/size
    x_pct: float = 0.5
    y_pct: float = 0.5
    w_pct: float = 0.2
    h_pct: float = 0.1
    use_background_blur: bool = False
    blur_intensity: int = 30

@dataclass
class BlurModel:
    id: str
    blur_type: str = "gaussian"  # Only gaussian now
    intensity: int = 30          # blur radius
    # Relative coordinates (0.0 - 1.0)
    x_pct: float = 0.5
    y_pct: float = 0.5
    w_pct: float = 0.2
    h_pct: float = 0.2
    rotation: float = 0.0
    corner_radius: int = 0
