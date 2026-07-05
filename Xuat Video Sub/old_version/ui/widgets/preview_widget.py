from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import QSizeF, Qt
from ui.widgets.draggable_block import DraggableBlock

class PreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #0d1117; border: none;") # Darker background

        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)
        
        self.block_widget = DraggableBlock()
        self.block_proxy = self.scene.addWidget(self.block_widget)
        self.block_proxy.setZValue(100) # Always on top
        
        # Position block near bottom initially
        self.block_widget.move(0, 200)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.setSceneRect(0, 0, self.width(), self.height())
        self.video_item.setSize(QSizeF(float(self.width()), float(self.height())))
        
        self.block_widget.parent_height = self.height()
        self.block_widget.setGeometry(0, self.block_widget.y(), self.width(), self.block_widget.height())
        if self.block_widget.y() + self.block_widget.height() > self.height() and self.height() > 0:
            self.block_widget.move(0, max(0, self.height() - self.block_widget.height()))

    @property
    def video_widget(self):
        return self.video_item
    
    @property
    def block(self):
        return self.block_widget
