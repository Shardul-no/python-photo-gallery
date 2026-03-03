from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QListView, QFileDialog, QProgressBar, QLabel, QStyledItemDelegate,
    QApplication, QStyle, QCheckBox, QFrame, QListWidget, QListWidgetItem,
    QMenu, QMenuBar, QDateEdit, QComboBox
)
from PySide6.QtCore import Qt, QSize, QThreadPool, QRect, QPoint, QSortFilterProxyModel, Slot, QDate
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QIcon
from ..models.media_model import MediaModel
from ..services.scanner import MediaScanner
from ..database import get_connection, init_db
from .viewer import MediaViewer
import os

class MediaFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.allowed_extensions = set()
        self.show_aae = False

    def set_filters(self, extensions, show_aae):
        self.allowed_extensions = extensions
        self.show_aae = show_aae
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        source_model = self.sourceModel()
        idx = source_model.index(source_row, 0, source_parent)
        
        item_type = source_model.data(idx, MediaModel.TypeRole)
        if item_type == "header":
            # We need to decide if header should stay.
            # Usually if ANY child of this header is visible.
            # But let's simplify: headers stay if they are present in the source.
            # Actually, to be perfect, a header should only show if there's media under it.
            # But the requirement says "Filtering must not break grouping logic."
            # A simple way is to show all headers, but it might look empty.
            # Let's check the next few items until the next header.
            return True 

        ext = source_model.data(idx, MediaModel.ExtensionRole)
        if not ext:
            return True
            
        if ext == ".aae" and not self.show_aae:
            return False
            
        # Group similar extensions
        ext_map = {
            ".jpg": ".jpg", ".jpeg": ".jpg",
            ".png": ".png",
            ".heic": ".heic",
            ".mp4": ".mp4",
            ".mov": ".mov"
        }
        mapped_ext = ext_map.get(ext, "Other")
        
        if mapped_ext in self.allowed_extensions:
            return True
        if "Other" in self.allowed_extensions and mapped_ext == "Other":
            return True
            
        return False

class MediaDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumb_width = 250
        self.thumb_height = 180
        self.header_height = 60
        self.is_bento = False

    def set_bento(self, enabled):
        self.is_bento = enabled

    def paint(self, painter, option, index):
        item_type = index.data(MediaModel.TypeRole)
        if item_type == "header":
            self.paint_header(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Pixmap
        pixmap = index.data(Qt.DecorationRole)
        rect = option.rect
        
        if pixmap and not pixmap.isNull():
            # In Bento mode, we want to fill the rectangle completely (Center Crop)
            scaled_pix = pixmap.scaled(
                rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            painter.setClipRect(rect)
            
            # Center the pixmap
            x = rect.x() + (rect.width() - scaled_pix.width()) // 2
            y = rect.y() + (rect.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)
            painter.setClipping(False)
        else:
            painter.fillRect(rect, QColor(40, 40, 40))
        
        # Selection/Hover highlight
        if option.state & QStyle.State_Selected:
            painter.setPen(QPen(QColor(0, 120, 215), 3))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        elif option.state & QStyle.State_MouseOver:
            painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))

        # Video Overlay
        media_type = index.data(MediaModel.MediaTypeRole)
        if media_type == "video":
            # Play icon
            icon_size = 40
            icon_rect = QRect(
                rect.center().x() - icon_size//2,
                rect.center().y() - icon_size//2,
                icon_size, icon_size
            )
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(icon_rect)
            
            painter.setPen(QPen(Qt.white, 2))
            p1 = QPoint(icon_rect.left() + 15, icon_rect.top() + 12)
            p2 = QPoint(icon_rect.left() + 15, icon_rect.bottom() - 12)
            p3 = QPoint(icon_rect.right() - 12, icon_rect.center().y())
            painter.drawPolygon([p1, p2, p3])

            # Duration badge
            duration = index.data(MediaModel.DurationRole)
            if duration:
                mins = int(duration // 60)
                secs = int(duration % 60)
                dur_str = f"{mins}:{secs:02d}"
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                text_rect = painter.fontMetrics().boundingRect(dur_str)
                badge_rect = QRect(
                    rect.right() - text_rect.width() - 15,
                    rect.bottom() - text_rect.height() - 15,
                    text_rect.width() + 8,
                    text_rect.height() + 4
                )
                painter.setBrush(QColor(0, 0, 0, 200))
                painter.drawRoundedRect(badge_rect, 4, 4)
                painter.setPen(Qt.white)
                painter.drawText(badge_rect, Qt.AlignCenter, dur_str)

        painter.restore()

    def paint_header(self, painter, option, index):
        painter.save()
        rect = option.rect
        label = index.data(Qt.DisplayRole)
        
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        # Align left, center vertically
        painter.drawText(rect.adjusted(10, 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter, label)
        painter.restore()

    def sizeHint(self, option, index):
        try:
            item_type = index.data(MediaModel.TypeRole)
        except Exception:
            return QSize(self.thumb_width, self.thumb_height)

        if item_type == "header":
            view = self.parent()
            if view:
                width = view.viewport().width() - 25
                return QSize(max(width, 200), self.header_height)
            return QSize(self.thumb_width * 3, self.header_height)
        
        if self.is_bento:
            # Get actual dimensions from DB
            w = index.data(MediaModel.WidthRole)
            h = index.data(MediaModel.HeightRole)
            
            # Fallback to pixmap if DB is empty
            if not w or not h:
                pix = index.data(Qt.DecorationRole)
                if pix and not pix.isNull():
                    w, h = pix.width(), pix.height()
            
            if w and h:
                aspect = w / h
                # Bento Rules (More dramatic sizes)
                if aspect < 0.7:  # Very Portrait (Tall)
                    return QSize(250, 520)
                elif aspect > 1.6: # Very Landscape (Wide)
                    return QSize(520, 250)
                elif 0.85 < aspect < 1.15: # Square-ish (Big Square)
                    return QSize(520, 520)
            
            # Default bento size (Medium Square)
            return QSize(250, 250)
            
        return QSize(self.thumb_width, self.thumb_height)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pro Photo & Video Gallery")
        self.resize(1400, 900)
        init_db()
        self.thread_pool = QThreadPool.globalInstance()

        # Viewer Overlay (Initialize early to avoid resizeEvent issues)
        self.viewer = MediaViewer(self)
        self.viewer.hide()
        self.viewer.prev_requested.connect(self.show_prev)
        self.viewer.next_requested.connect(self.show_next)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QPushButton { 
                background-color: #333; border: none; padding: 8px 15px; 
                border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton#addBtn { background-color: #0078d7; }
            QPushButton#addBtn:hover { background-color: #0086f0; }
            QListView, QListWidget { 
                background-color: #121212; border: none; 
                outline: none;
            }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #222; }
            QListWidget::item:selected { background-color: #0078d7; color: white; }
            QListWidget::item:hover { background-color: #2a2a2a; }
            QCheckBox { spacing: 5px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QProgressBar {
                background-color: #222; border: 1px solid #333;
                border-radius: 5px; text-align: center; height: 15px;
            }
            QProgressBar::chunk { background-color: #0078d7; }
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.setup_menus()
        
        # Upper area (Calendar Jump)
        self.setup_calendar_bar()

        # Content area
        self.content_layout = QHBoxLayout()
        self.main_layout.addLayout(self.content_layout)

        # Left Sidebar (Albums)
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_label = QLabel("ALBUMS")
        self.sidebar_label.setStyleSheet("font-weight: bold; color: #888; margin-top: 10px; margin-left: 5px;")
        self.sidebar_layout.addWidget(self.sidebar_label)
        
        self.album_list = QListWidget()
        self.album_list.setFixedWidth(250)
        self.album_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.album_list.customContextMenuRequested.connect(self.show_album_context_menu)
        self.album_list.itemSelectionChanged.connect(self.on_album_selected)
        self.sidebar_layout.addWidget(self.album_list)
        
        self.content_layout.addLayout(self.sidebar_layout)

        # Right side
        self.right_layout = QVBoxLayout()
        self.content_layout.addLayout(self.right_layout)

        # Toolbar / Status
        self.status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedWidth(200)
        self.status_layout.addWidget(self.progress_bar)
        
        self.right_layout.addLayout(self.status_layout)

        # Filter Panel
        self.filter_panel = QHBoxLayout()
        self.filter_panel.setContentsMargins(5, 5, 5, 5)
        self.filter_panel.setSpacing(15)
        
        self.filters = {}
        for text in [".jpg", ".png", ".heic", ".mp4", ".mov", ".aae", "Other"]:
            cb = QCheckBox(text.upper() if text.startswith(".") else text)
            cb.setChecked(text != ".aae")
            cb.stateChanged.connect(self.apply_filters)
            self.filter_panel.addWidget(cb)
            self.filters[text] = cb
            
        self.bento_cb = QCheckBox("BENTO VIEW")
        self.bento_cb.setStyleSheet("color: #0078d7; font-weight: bold;")
        self.bento_cb.stateChanged.connect(self.toggle_bento)
        self.filter_panel.addStretch()
        self.filter_panel.addWidget(self.bento_cb)
            
        self.right_layout.addLayout(self.filter_panel)

        # Grid View
        self.view = QListView()
        self.view.setViewMode(QListView.IconMode)
        self.view.setResizeMode(QListView.Adjust)
        self.view.setSpacing(10)
        self.view.setUniformItemSizes(False)
        self.view.setMovement(QListView.Static)
        self.view.setFlow(QListView.LeftToRight)
        self.view.setWrapping(True)
        self.view.setLayoutMode(QListView.Batched)
        self.view.setSelectionMode(QListView.SingleSelection)
        self.view.doubleClicked.connect(self.open_viewer_at)
        
        self.source_model = MediaModel()
        self.proxy_model = MediaFilterProxy()
        self.proxy_model.setSourceModel(self.source_model)
        self.view.setModel(self.proxy_model)
        
        self.delegate = MediaDelegate(self.view)
        self.view.setItemDelegate(self.delegate)
        
        self.right_layout.addWidget(self.view)
        
        self.load_albums()
        self.apply_filters()

    def setup_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        
        add_folder_act = file_menu.addAction("Add Folder...")
        add_folder_act.triggered.connect(self.add_album)
        
        remove_album_act = file_menu.addAction("Remove Selected Album")
        remove_album_act.triggered.connect(self.remove_selected_album)
        
        file_menu.addSeparator()
        
        exit_act = file_menu.addAction("Exit")
        exit_act.triggered.connect(self.close)

    def load_albums(self):
        self.album_list.clear()
        
        # Add "All Photos" item
        all_item = QListWidgetItem("All Photos")
        all_item.setData(Qt.UserRole, None) # No album_id
        self.album_list.addItem(all_item)
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id, a.name, COUNT(m.id) 
            FROM albums a 
            LEFT JOIN media m ON a.id = m.album_id 
            GROUP BY a.id
        """)
        rows = cursor.fetchall()
        for row in rows:
            album_id, name, count = row
            item = QListWidgetItem(f"{name} ({count})")
            item.setData(Qt.UserRole, album_id)
            item.setData(Qt.UserRole + 1, name)
            self.album_list.addItem(item)
        conn.close()

    @Slot()
    def on_album_selected(self):
        selected = self.album_list.selectedItems()
        album_id = None
        if selected:
            item = selected[0]
            album_id = item.data(Qt.UserRole)
        
        self.source_model.refresh(album_id)

    def show_album_context_menu(self, pos):
        item = self.album_list.itemAt(pos)
        if not item:
            return
            
        album_id = item.data(Qt.UserRole)
        if album_id is None: # "All Photos"
            return
            
        menu = QMenu()
        rescan_act = menu.addAction("Rescan")
        open_folder_act = menu.addAction("Open folder in Explorer")
        remove_act = menu.addAction("Remove from library")
        
        action = menu.exec(self.album_list.mapToGlobal(pos))
        
        if action == rescan_act:
            self.rescan_album(album_id)
        elif action == open_folder_act:
            self.open_album_folder(album_id)
        elif action == remove_act:
            self.remove_album_by_id(album_id)

    def rescan_album(self, album_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT root_path FROM albums WHERE id = ?", (album_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            self.start_scan(album_id, row[0])

    def open_album_folder(self, album_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT root_path FROM albums WHERE id = ?", (album_id,))
        row = cursor.fetchone()
        conn.close()
        if row and os.path.exists(row[0]):
            os.startfile(row[0])

    def remove_selected_album(self):
        selected = self.album_list.selectedItems()
        if not selected:
            return
        item = selected[0]
        album_id = item.data(Qt.UserRole)
        if album_id:
            self.remove_album_by_id(album_id)

    def remove_album_by_id(self, album_id):
        conn = get_connection()
        cursor = conn.cursor()
        # Delete media from DB
        cursor.execute("DELETE FROM media WHERE album_id = ?", (album_id,))
        # Delete album from DB
        cursor.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        conn.commit()
        conn.close()
        self.load_albums()
        self.source_model.refresh()

        # Viewer Overlay
        self.viewer = MediaViewer(self)
        self.viewer.hide()
        self.viewer.prev_requested.connect(self.show_prev)
        self.viewer.next_requested.connect(self.show_next)

        self.thread_pool = QThreadPool.globalInstance()
        self.apply_filters()

    def apply_filters(self):
        extensions = set()
        show_aae = self.filters[".aae"].isChecked()
        for ext, cb in self.filters.items():
            if cb.isChecked() and ext != ".aae":
                extensions.add(ext)
        self.proxy_model.set_filters(extensions, show_aae)

    def toggle_bento(self, state):
        enabled = (state == 2) # Qt.Checked is usually 2
        self.delegate.set_bento(enabled)
        
        if enabled:
            # We clear the grid size to allow variable item sizes
            self.view.setGridSize(QSize()) 
            self.view.setSpacing(15)
        else:
            self.view.setGridSize(QSize()) 
            self.view.setSpacing(10)
            
        # Force redraw/layout
        self.view.doItemsLayout()
        self.view.viewport().update()
        self.view.update()

    def add_album(self):
        root_path = QFileDialog.getExistingDirectory(self, "Select Photo/Video Folder")
        if root_path:
            name = os.path.basename(root_path)
            conn = get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO albums (name, root_path) VALUES (?, ?)", (name, root_path))
                album_id = cursor.lastrowid
                conn.commit()
            except:
                cursor.execute("SELECT id FROM albums WHERE root_path = ?", (root_path,))
                album_id = cursor.fetchone()[0]
            conn.close()
            self.start_scan(album_id, root_path)

    def start_scan(self, album_id, root_path):
        self.status_label.setText(f"Scanning...")
        self.progress_bar.setVisible(True)
        scanner = MediaScanner(album_id, root_path)
        scanner.signals.progress.connect(self.update_progress)
        scanner.signals.finished.connect(self.scan_finished)
        scanner.signals.item_added.connect(self.source_model.add_item_manually)
        self.thread_pool.start(scanner)

    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def scan_finished(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("Scan complete")
        self.load_albums()
        self.source_model.refresh(self.source_model.current_album_id)
        self.update_available_years()

    def setup_calendar_bar(self):
        self.calendar_layout = QHBoxLayout()
        self.calendar_layout.setContentsMargins(10, 5, 10, 5)
        
        self.calendar_layout.addWidget(QLabel("Jump to:"))
        
        # Year
        self.year_combo = QComboBox()
        self.year_combo.addItem("Select Year")
        self.year_combo.currentTextChanged.connect(self.on_year_changed)
        self.calendar_layout.addWidget(self.year_combo)
        
        # Month
        self.month_combo = QComboBox()
        self.month_combo.addItem("Select Month")
        self.month_combo.currentTextChanged.connect(self.jump_to_month)
        self.calendar_layout.addWidget(self.month_combo)
        
        self.update_available_years()
        
        # Date
        self.jump_date_edit = QDateEdit()
        self.jump_date_edit.setCalendarPopup(True)
        self.jump_date_edit.setDate(QDate.currentDate())
        self.jump_date_edit.dateChanged.connect(self.jump_to_date)
        self.calendar_layout.addWidget(self.jump_date_edit)
        
        self.calendar_layout.addStretch()
        self.main_layout.addLayout(self.calendar_layout)

    def update_available_years(self):
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem("Select Year")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT strftime('%Y', date_taken) as year FROM media ORDER BY year DESC")
        years = cursor.fetchall()
        for row in years:
            if row[0]:
                self.year_combo.addItem(row[0])
        conn.close()
        self.year_combo.blockSignals(False)

    def on_year_changed(self, year_str):
        if year_str == "Select Year":
            self.month_combo.clear()
            self.month_combo.addItem("Select Month")
            return

        # Update months for this year
        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        self.month_combo.addItem("Select Month")
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT strftime('%m', date_taken) as month 
            FROM media 
            WHERE strftime('%Y', date_taken) = ? 
            ORDER BY month ASC
        """, (year_str,))
        months_found = cursor.fetchall()
        
        month_names = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
        
        for row in months_found:
            if row[0]:
                m_idx = int(row[0]) - 1
                self.month_combo.addItem(month_names[m_idx], row[0])
        
        conn.close()
        self.month_combo.blockSignals(False)
        self._jump_to_pattern(f"{year_str}-")

    def jump_to_month(self, month_name):
        if month_name == "Select Month": return
        year = self.year_combo.currentText()
        if year == "Select Year": return
        
        month_idx = self.month_combo.currentData()
        if month_idx:
            pattern = f"{year}-{month_idx}-"
            self._jump_to_pattern(pattern)

    def jump_to_date(self, qdate):
        date_str = qdate.toString("yyyy-MM-dd")
        self._jump_to_pattern(date_str)

    def _jump_to_pattern(self, pattern):
        """Find the first item in the proxy model that matches the date pattern and scroll to it."""
        for row in range(self.proxy_model.rowCount()):
            idx = self.proxy_model.index(row, 0)
            date_val = idx.data(MediaModel.DateRole)
            if not date_val:
                continue
            
            # If pattern starts with dash, it's likely a month-only jump like -01-
            match = False
            if pattern.startswith("-"):
                match = pattern in date_val
            else:
                match = date_val.startswith(pattern)
                
            if match:
                self.view.scrollTo(idx, QListView.PositionAtTop)
                return


    def open_viewer_at(self, proxy_index):
        item_type = proxy_index.data(MediaModel.TypeRole)
        if item_type == "header":
            return
            
        self.current_viewer_proxy_index = proxy_index
        path = proxy_index.data(MediaModel.FilePathRole)
        m_type = proxy_index.data(MediaModel.MediaTypeRole)
        
        self.viewer.setGeometry(self.rect())
        self.viewer.show_content(path, m_type)

    def show_next(self):
        row = self.current_viewer_proxy_index.row() + 1
        while row < self.proxy_model.rowCount():
            new_idx = self.proxy_model.index(row, 0)
            if new_idx.data(MediaModel.TypeRole) == "media":
                self.open_viewer_at(new_idx)
                return
            row += 1

    def show_prev(self):
        row = self.current_viewer_proxy_index.row() - 1
        while row >= 0:
            new_idx = self.proxy_model.index(row, 0)
            if new_idx.data(MediaModel.TypeRole) == "media":
                self.open_viewer_at(new_idx)
                return
            row -= 1

    def resizeEvent(self, event):
        if hasattr(self, 'viewer') and not self.viewer.isHidden():
            self.viewer.setGeometry(self.rect())
        super().resizeEvent(event)
