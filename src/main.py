import sys
import os
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMainWindow,
    QToolButton,
)


# Helper function: Convert text to path
def text_to_path(text, font_family="Arial", font_size=50):
    font = QFont(font_family, font_size)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    return path


# Helper function: Convert path to G-Code
def path_to_gcode(path: QPainterPath, scale=0.1, safe_z=5.0, cut_z=0.0, feedrate=500):
    gcode = [
        "G21 ; mm mode",
        "G90 ; absolute positioning"
    ]

    if path.elementCount() == 0:
        return "\n".join(gcode)

    pen_down = False

    for i in range(path.elementCount()):
        elem = path.elementAt(i)

        x = elem.x * scale
        y = -elem.y * scale  # Invert Y-axis for CNC

        if elem.type == QPainterPath.ElementType.MoveToElement:
            if pen_down:
                gcode.append(f"G0 Z{safe_z:.2f}")  # Pen up
                pen_down = False
            gcode.append(f"G0 X{x:.2f} Y{y:.2f}")  # Position

        else:  # LineTo or CurveTo
            if not pen_down:
                gcode.append(f"G1 Z{cut_z:.2f} F{feedrate}")  # Pen down
                pen_down = True
            gcode.append(f"G1 X{x:.2f} Y{y:.2f} F{feedrate}")

    if pen_down:
        gcode.append(f"G0 Z{safe_z:.2f}")  # Pen up at the end

    gcode.append("M2 ; Program end")
    return "\n".join(gcode)


class PreviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.path = None
        self.line_width = 0.6  # Default 0.6 mm
        self.is_dark_mode = False
        self.setMinimumSize(QSize(300, 200))

    def set_path(self, path: QPainterPath):
        self.path = path
        self.update()

    def set_line_width(self, width):
        self.line_width = width
        self.update()

    def set_theme(self, is_dark):
        self.is_dark_mode = is_dark
        self.update()

    def paintEvent(self, event):
        if not self.path:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Set background color based on theme
        if self.is_dark_mode:
            painter.fillRect(self.rect(), QColor(30, 30, 30))
        else:
            painter.fillRect(self.rect(), QColor(240, 240, 240))

        # Calculate scaling and centering
        bounds = self.path.boundingRect()
        view_scale = min(self.width() / bounds.width(), self.height() / bounds.height()) * 0.9

        # G-Code scale factor (from path_to_gcode)
        gcode_scale = 0.1

        # Apply transformations for centering and scaling
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(view_scale, view_scale)
        painter.translate(-bounds.center().x(), -bounds.center().y())

        # Set pen AFTER transformations
        # QPainter applies transformations to geometry but not to pen width
        # Therefore, line width must be adjusted by the transformation scale
        pen_color = QColor(240, 240, 240) if self.is_dark_mode else QColor(30, 30, 30)
        pen = QPen(pen_color)
        scaled_width = self.line_width / gcode_scale / view_scale
        pen.setWidthF(scaled_width)
        painter.setPen(pen)

        # Draw path
        painter.drawPath(self.path)


class GCodeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Text2Gcode")
        self.resize(900, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Set initial theme
        self.is_dark_mode = False

        # Create status bar for messages
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Input Group
        input_group = QGroupBox("Text Input")
        input_layout = QVBoxLayout()

        # Font selection field
        font_layout = QHBoxLayout()
        font_label = QLabel("Font:")
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Arial"))
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_combo, 1)
        input_layout.addLayout(font_layout)

        # Text input field
        text_label = QLabel("Enter Text:")
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type your text here...")
        input_layout.addWidget(text_label)
        input_layout.addWidget(self.text_input)

        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # Size & Dimensions Group
        size_group = QGroupBox("Size Configuration")
        size_layout = QVBoxLayout()

        # Font size input field
        size_layout_h = QHBoxLayout()
        size_label = QLabel("Font size:")
        self.size_spin = QSpinBox()
        self.size_spin.setRange(10, 500)
        self.size_spin.setValue(100)
        size_layout_h.addWidget(size_label)
        size_layout_h.addWidget(self.size_spin)
        size_layout_h.addStretch(1)
        size_layout.addLayout(size_layout_h)

        # Maximum dimensions input fields
        max_dim_layout = QHBoxLayout()
        self.max_dim_check = QCheckBox("Max. Dimensions:")
        self.max_width_spin = QDoubleSpinBox()
        self.max_width_spin.setRange(10, 1000)
        self.max_width_spin.setValue(100)
        self.max_width_spin.setSuffix(" mm")
        width_label = QLabel("width:")
        self.max_height_spin = QDoubleSpinBox()
        self.max_height_spin.setRange(10, 1000)
        self.max_height_spin.setValue(50)
        self.max_height_spin.setSuffix(" mm")
        height_label = QLabel("height:")
        max_dim_layout.addWidget(self.max_dim_check)
        max_dim_layout.addWidget(width_label)
        max_dim_layout.addWidget(self.max_width_spin)
        max_dim_layout.addWidget(height_label)
        max_dim_layout.addWidget(self.max_height_spin)
        max_dim_layout.addStretch(1)
        size_layout.addLayout(max_dim_layout)

        # Line width input field
        line_width_layout = QHBoxLayout()
        line_width_label = QLabel("Line width:")
        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.1, 5.0)
        self.line_width_spin.setValue(0.6)
        self.line_width_spin.setSingleStep(0.1)
        self.line_width_spin.valueChanged.connect(self.update_line_width)
        line_width_layout.addWidget(line_width_label)
        line_width_layout.addWidget(self.line_width_spin)
        line_width_layout.addStretch(1)
        size_layout.addLayout(line_width_layout)

        size_group.setLayout(size_layout)
        main_layout.addWidget(size_group)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.generate_button = QPushButton("Generate G-Code")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.clicked.connect(self.generate_gcode)
        actions_layout.addWidget(self.generate_button)

        # Theme toggle button
        self.theme_button = QToolButton()
        self.theme_button.setText("🌙" if not self.is_dark_mode else "☀️")
        self.theme_button.setMinimumHeight(40)
        self.theme_button.setMinimumWidth(40)
        self.theme_button.clicked.connect(self.toggle_theme)
        actions_layout.addWidget(self.theme_button)

        main_layout.addLayout(actions_layout)

        # Results Group - preview and code
        results_group = QGroupBox("Results")
        results_layout = QHBoxLayout()

        # Preview widget
        preview_layout = QVBoxLayout()
        preview_label = QLabel("Preview:")
        self.preview = PreviewWidget()
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.preview, 1)
        results_layout.addLayout(preview_layout, 3)

        # G-code output
        gcode_layout = QVBoxLayout()
        gcode_label = QLabel("G-Code Output:")
        self.gcode_preview = QTextEdit()
        self.gcode_preview.setFont(QFont("Courier", 10))
        self.gcode_preview.setReadOnly(True)
        gcode_layout.addWidget(gcode_label)
        gcode_layout.addWidget(self.gcode_preview, 1)

        # Output action buttons
        output_actions = QHBoxLayout()
        self.copy_button = QPushButton("Copy G-Code")
        self.copy_button.clicked.connect(self.copy_gcode)
        self.save_button = QPushButton("Save G-Code")
        self.save_button.clicked.connect(self.save_gcode)
        output_actions.addWidget(self.copy_button)
        output_actions.addWidget(self.save_button)
        gcode_layout.addLayout(output_actions)

        results_layout.addLayout(gcode_layout, 2)
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group, 1)

        # Info label for dimensions
        self.dimensions_label = QLabel("Dimensions: - x - mm")
        main_layout.addWidget(self.dimensions_label)

        self.setCentralWidget(central_widget)

        # Apply initial theme
        self.apply_theme()

    def update_line_width(self):
        self.preview.set_line_width(self.line_width_spin.value())

    def generate_gcode(self):
        text = self.text_input.text()
        if not text.strip():
            self.status_bar.showMessage("Please enter some text", 3000)
            return

        font_family = self.font_combo.currentFont().family()
        font_size = self.size_spin.value()
        scale = 0.1  # Same scale as in path_to_gcode

        # Check if max. dimensions are enabled
        if self.max_dim_check.isChecked():
            max_width_mm = self.max_width_spin.value()
            max_height_mm = self.max_height_spin.value()

            # Binary search for optimal font size
            min_size = 1
            max_size = 500
            optimal_size = font_size

            while min_size <= max_size:
                mid_size = (min_size + max_size) // 2
                test_path = text_to_path(text, font_family=font_family, font_size=mid_size)
                bounds = test_path.boundingRect()

                width_mm = bounds.width() * scale
                height_mm = bounds.height() * scale

                if width_mm <= max_width_mm and height_mm <= max_height_mm:
                    # This size fits, try going larger
                    optimal_size = mid_size
                    min_size = mid_size + 1
                else:
                    # This size is too big, try going smaller
                    max_size = mid_size - 1

            # Use the optimal size
            font_size = optimal_size
            self.size_spin.setValue(font_size)  # Update UI

        path = text_to_path(text, font_family=font_family, font_size=font_size)
        self.preview.set_path(path)

        # Calculate dimensions
        bounds = path.boundingRect()
        width_mm = bounds.width() * scale
        height_mm = bounds.height() * scale
        self.dimensions_label.setText(f"Dimensions: {width_mm:.2f} x {height_mm:.2f} mm")

        gcode = path_to_gcode(path, scale=scale)
        self.gcode_preview.setPlainText(gcode)

        self.status_bar.showMessage("G-code generated successfully", 3000)

    def copy_gcode(self):
        gcode = self.gcode_preview.toPlainText()
        if gcode:
            clipboard = QApplication.clipboard()
            clipboard.setText(gcode)
            self.status_bar.showMessage("G-code copied to clipboard", 3000)

    def save_gcode(self):
        gcode = self.gcode_preview.toPlainText()
        if not gcode:
            self.status_bar.showMessage("No G-code to save", 3000)
            return

        # Default name from LineEdit text
        default_name = self.text_input.text().strip()
        if not default_name:
            default_name = "gcode"

        # Suggest filename
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save G-Code",
            f"{default_name}.g",
            "G-Code Files (*.g *.gcode);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w') as file:
                    file.write(gcode)
                self.status_bar.showMessage(f"G-code saved as {filename}", 3000)
            except Exception as e:
                self.status_bar.showMessage(f"Error saving: {e}", 5000)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.theme_button.setText("☀️" if self.is_dark_mode else "🌙")
        self.apply_theme()
        self.preview.set_theme(self.is_dark_mode)

    def apply_theme(self):
        if self.is_dark_mode:
            # Dark theme
            stylesheet = """
            QMainWindow, QWidget {
                background-color: #2d2d2d;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox {
                background-color: #3d3d3d;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 5px;
            }
            QPushButton, QToolButton {
                background-color: #505050;
                color: #e0e0e0;
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #606060;
                border: 1px solid #7a7a7a;
            }
            QPushButton:pressed, QToolButton:pressed {
                background-color: #404040;
            }
            QTextEdit {
                font-family: "Courier";
                background-color: #252525;
                color: #e0e0e0;
                border: 1px solid #555555;
            }
            QStatusBar {
                background-color: #353535;
                color: #e0e0e0;
            }
            """
        else:
            # Light theme
            stylesheet = """
            QMainWindow, QWidget {
                background-color: #f0f0f0;
                color: #202020;
            }
            QGroupBox {
                border: 1px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox {
                background-color: white;
                color: #202020;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 2px 5px;
            }
            QPushButton, QToolButton {
                background-color: #e0e0e0;
                color: #202020;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #d0d0d0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed, QToolButton:pressed {
                background-color: #c0c0c0;
            }
            QTextEdit {
                font-family: "Courier";
                background-color: white;
                color: #202020;
                border: 1px solid #c0c0c0;
            }
            QStatusBar {
                background-color: #e0e0e0;
                color: #202020;
            }
            """

        # Set the stylesheet
        self.setStyleSheet(stylesheet)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GCodeApp()
    window.show()
    sys.exit(app.exec())
