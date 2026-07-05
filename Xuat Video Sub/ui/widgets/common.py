from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QColor, QBrush, QCursor

class ResizableGraphicsRectItem(QGraphicsRectItem):
    handle_size = 10.0
    
    def __init__(self, rect, parent=None):
        super().__init__(rect, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.resizing = False
        self.resize_dir = None
        self.start_rect = None
        self.start_pos = None

    def paint(self, painter, option, widget):
        if self.isSelected():
            painter.setPen(self.pen())
            painter.setBrush(self.brush())
            painter.drawRect(self.rect())

    def _get_handle_rects(self):
        r = self.rect()
        s = self.handle_size
        return {
            'tl': QRectF(r.left(), r.top(), s, s),
            'tr': QRectF(r.right() - s, r.top(), s, s),
            'bl': QRectF(r.left(), r.bottom() - s, s, s),
            'br': QRectF(r.right() - s, r.bottom() - s, s, s),
            't': QRectF(r.left() + s, r.top(), r.width() - 2*s, s),
            'b': QRectF(r.left() + s, r.bottom() - s, r.width() - 2*s, s),
            'l': QRectF(r.left(), r.top() + s, s, r.height() - 2*s),
            'r': QRectF(r.right() - s, r.top() + s, s, r.height() - 2*s),
        }

    def hoverMoveEvent(self, event):
        pos = event.pos()
        handles = self._get_handle_rects()
        if handles['tl'].contains(pos) or handles['br'].contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif handles['tr'].contains(pos) or handles['bl'].contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
        elif handles['t'].contains(pos) or handles['b'].contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        elif handles['l'].contains(pos) or handles['r'].contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if hasattr(self, 'on_interaction'):
            self.on_interaction()
            
        # Prevent multi-selection dragging issues
        if self.scene():
            for item in self.scene().selectedItems():
                if item != self:
                    item.setSelected(False)
        self.setSelected(True)
            
        pos = event.pos()
        handles = self._get_handle_rects()
        self.resize_dir = None
        for d, r in handles.items():
            if r.contains(pos):
                self.resize_dir = d
                break
                
        if self.resize_dir:
            self.resizing = True
            self.start_rect = self.rect()
            self.start_pos = event.scenePos()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            diff = event.scenePos() - self.start_pos
            r = QRectF(self.start_rect)
            
            if 't' in self.resize_dir:
                r.setTop(r.top() + diff.y())
            if 'b' in self.resize_dir:
                r.setBottom(r.bottom() + diff.y())
            if 'l' in self.resize_dir:
                r.setLeft(r.left() + diff.x())
            if 'r' in self.resize_dir:
                r.setRight(r.right() + diff.x())
                
            if r.width() < self.handle_size * 2:
                if 'l' in self.resize_dir: r.setLeft(r.right() - self.handle_size * 2)
                else: r.setRight(r.left() + self.handle_size * 2)
            if r.height() < self.handle_size * 2:
                if 't' in self.resize_dir: r.setTop(r.bottom() - self.handle_size * 2)
                else: r.setBottom(r.top() + self.handle_size * 2)
                
            self.setRect(r)
            if hasattr(self, 'on_geometry_changed'):
                self.on_geometry_changed()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.resizing = False
        super().mouseReleaseEvent(event)
        
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged or change == QGraphicsItem.GraphicsItemChange.ItemScaleHasChanged:
            if hasattr(self, 'on_geometry_changed'):
                self.on_geometry_changed()
        return super().itemChange(change, value)
