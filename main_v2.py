import sys
import os
import mss
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QPushButton, QLabel, QTextEdit, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image
import requests
from io import BytesIO
import json
import time

ENDPOINT = "http://localhost:8000"
PARSE_API = "parse-screenshot"
SCREENSHOT_DIR = os.path.expanduser("~/Desktop/screenshots")

class NetworkWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def process_request(self):
        try:
            self.progress.emit("Sending file to server...")
            files = {
                'file': (os.path.basename(self.file_path), 
                        open(self.file_path, 'rb'), 
                        'image/png')
            }
            
            response = requests.post(f"{ENDPOINT}/{PARSE_API}", files=files)
            data = response.json()
            
            if 'labeled_image_path' in data:
                self.progress.emit("Downloading labeled image...")
                labeled_image_path = data['labeled_image_path']
                img_response = requests.get(f"{ENDPOINT}/{labeled_image_path}")
                
                # Save the labeled image
                image_name = os.path.basename(labeled_image_path)
                downloaded_image_path = os.path.join(SCREENSHOT_DIR, image_name)
                with open(downloaded_image_path, 'wb') as f:
                    f.write(img_response.content)
                data['downloaded_image_path'] = downloaded_image_path

            self.finished.emit(data)
            
        except Exception as e:
            self.error.emit(str(e))

class NetworkThread(QThread):
    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.worker.moveToThread(self)

    def run(self):
        self.worker.process_request()

class ScreenshotApp(QMainWindow):
    def __init__(self):
        # Create screenshots directory
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

        # Initialize main window
        super().__init__()
        self.setWindowTitle("Screenshot Parser")
        self.setFixedSize(1000, 700)
        self.setStyleSheet("background-color: #ffffff;")
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.layout = QVBoxLayout(main_widget)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(20, 20, 20, 20)

        # Create image display area
        self.image_frame = QFrame()
        self.image_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.image_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 2px solid #999;
                border-radius: 5px;
            }
        """)
        self.image_frame.setFixedSize(960, 450)

        # Image label
        self.image_label = QLabel("Image will appear here")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_layout = QVBoxLayout(self.image_frame)
        image_layout.addWidget(self.image_label)

        # Text area
        self.text_area = QTextEdit()
        self.text_area.setFixedHeight(150)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 0px solid #999;
                border-radius: 15px;
                padding: 5px;
            }
        """)
        # self.text_area.setText("Ready to take screenshot...")

        # Screenshot button
        self.screenshot_button = QPushButton("Take Screenshot")
        self.screenshot_button.setFixedSize(200, 50)
        self.screenshot_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.screenshot_button.clicked.connect(self.take_screenshot)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(200, 20)
        self.progress_bar.hide()

        # Add widgets to layout
        self.layout.addWidget(self.text_area)
        self.layout.addWidget(self.screenshot_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.progress_bar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Initialize thread-related variables
        self.network_thread = None
        self.network_worker = None

    def take_screenshot(self):
        try:
            print("\n[DEBUG] Starting screenshot capture...")
            self.text_area.setText("Taking screenshot...")
            
            # Minimize window temporarily
            print("[DEBUG] Minimizing window...")
            self.showMinimized()
            self.hide()
            QApplication.processEvents()
            
            # Take screenshot
            file_path = os.path.join(SCREENSHOT_DIR, "screenshot.png")
            print(f"[DEBUG] Screenshot will be saved to: {file_path}")
            with mss.mss() as sct:
                print("[DEBUG] MSS initialized")
                monitor = sct.monitors[0]
                bbox = {
                    'top': 0, 
                    'left': 0, 
                    'width': monitor['width'], 
                    'height': monitor['height']
                }
                sct_img = sct.grab(bbox)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=file_path)
                print("[DEBUG] Screenshot saved successfully")

            # Show window again
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.showNormal()
            
            # Display the screenshot
            self.display_image(file_path)
            self.text_area.append(f"\nScreenshot saved to: {file_path}")
            
            # Start network request in background
            self.start_network_request(file_path)

        except Exception as e:
            print(f"[ERROR] Screenshot capture failed: {str(e)}")
            self.text_area.setText(f"Error: {str(e)}")
            self.show()
            self.showNormal()

    def start_network_request(self, file_path):
        # Clean up any existing thread
        if self.network_thread is not None:
            self.network_thread.quit()
            self.network_thread.wait()

        # Create new worker and thread
        self.network_worker = NetworkWorker(file_path)
        self.network_thread = NetworkThread(self.network_worker)

        # Connect signals
        self.network_worker.finished.connect(self.handle_network_response)
        self.network_worker.error.connect(self.handle_network_error)
        self.network_worker.progress.connect(self.handle_progress_update)
        self.network_thread.finished.connect(self.cleanup_network_thread)

        # Show progress bar and start thread
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.show()
        self.screenshot_button.setEnabled(False)
        self.network_thread.start()

    def handle_network_response(self, data):
        try:
            # Process the parsed content
            if 'parsed_content_list' in data:
                parsed_content_list = data["parsed_content_list"]
                content_text = '\n'.join([
                    f'type: {x["type"]}, content: {x["content"]}, interactivity: {x["interactivity"]}' 
                    for x in parsed_content_list
                ])
                self.text_area.setText(content_text)

            # Display the labeled image if available
            if 'downloaded_image_path' in data:
                self.display_image(data['downloaded_image_path'])

        except Exception as e:
            print(f"[ERROR] Failed to process network response: {str(e)}")
            self.text_area.append(f"\nError processing response: {str(e)}")

        finally:
            self.progress_bar.hide()
            self.screenshot_button.setEnabled(True)

    def handle_network_error(self, error_message):
        self.text_area.append(f"\nNetwork error: {error_message}")
        self.progress_bar.hide()
        self.screenshot_button.setEnabled(True)

    def handle_progress_update(self, message):
        self.text_area.append(f"\n{message}")

    def cleanup_network_thread(self):
        self.network_thread = None
        self.network_worker = None

    def display_image(self, image_path):
        print(f"\n[DEBUG] display_image: Loading image from {image_path}")
        try:
            # Insert image on top
            if self.image_frame not in [child for child in self.layout.children()]:
                self.layout.insertWidget(0, self.image_frame)

            # Load and resize image
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(
                940, 440,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            print("[DEBUG] Image displayed successfully")
        except Exception as e:
            print(f"[ERROR] Failed to display image: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()