import sys
import os
import mss
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QPushButton, QLabel, QTextEdit, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image
import requests
from io import BytesIO
import json
import time

ENDPOINT = "http://localhost:8000"
PARSE_API = "parse-screenshot"
SCREENSHOT_DIR = os.path.expanduser("~/Desktop/screenshots")

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
        # Add widgets to layout
        # layout.addWidget(self.image_frame)
        self.layout.addWidget(self.text_area)
        self.layout.addWidget(self.screenshot_button, alignment=Qt.AlignmentFlag.AlignCenter)




    def take_screenshot(self):
        try:
            print("\n[DEBUG] Starting screenshot capture...")
            self.text_area.setText("Taking screenshot...")
            # -- Minimize window temporarily
            print("[DEBUG] Minimizing window...")
            self.showMinimized()
            self.hide()
            QApplication.processEvents()  # Process any pending events
            # -- Take screenshot
            file_path = os.path.join(SCREENSHOT_DIR, "screenshot.png")
            print(f"[DEBUG] Screenshot will be saved to: {file_path}")
            with mss.mss() as sct:
                print("[DEBUG] MSS initialized")
                monitor = sct.monitors[0]  # Use primary monitor
                print(f"[DEBUG] Monitor details: {monitor}")
                bbox = {
                    'top': 0, 
                    'left': 0, 
                    'width': monitor['width'], 
                    'height': monitor['height']
                }
                print(f"[DEBUG] Capture bbox: {bbox}")
                sct_img = sct.grab(bbox)
                print("[DEBUG] Screenshot captured, saving to file...")
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=file_path)
                print("[DEBUG] Screenshot saved successfully")
            #  -- Show window again
            print("[DEBUG] Restoring window...")
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.showNormal()
            # -- Display the screenshot
            print("[DEBUG] Displaying captured screenshot...")
            self.display_image(file_path)
            self.text_area.append(f"\nScreenshot saved to: {file_path}")
            print("[DEBUG] Screenshot displayed in UI")
            # Optional: Send to server

            self.send_request(file_path)
        except Exception as e:
            print(f"[ERROR] Screenshot capture failed: {str(e)}")
            print(f"[ERROR] Exception type: {type(e)}")
            import traceback
            print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            self.text_area.setText(f"Error: {str(e)}")
            self.show()
            self.showNormal()


    def display_image(self, image_path):
        print(f"\n[DEBUG] display_image: Loading image from {image_path}")
        try:
            # Insert image on top
            if self.image_frame not in [child for child in self.layout.children()]:
                self.layout.insertWidget(0, self.image_frame)
            # Load and resize image while maintaining aspect ratio
            pixmap = QPixmap(image_path)
            print(f"[DEBUG] Original image size: {pixmap.width()}x{pixmap.height()}")
            
            scaled_pixmap = pixmap.scaled(
                940, 440,  # Slightly smaller than frame
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            print(f"[DEBUG] Scaled image size: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
            self.image_label.setPixmap(scaled_pixmap)
            print("[DEBUG] Image displayed successfully")
        except Exception as e:
            print(f"[ERROR] Failed to display image: {str(e)}")
            print(f"[ERROR] Exception type: {type(e)}")
            import traceback
            print(f"[ERROR] Traceback:\n{traceback.format_exc()}")


    def send_request(self, file_path):
        print(f"\n[DEBUG] send_request: Sending file {file_path} to server")
        try:
            files = {
                'file': (os.path.basename(file_path), 
                        open(file_path, 'rb'), 
                        'image/png')
            }
            self.__toggleProgressBar()
            print(f"[DEBUG] Making POST request to {ENDPOINT}/{PARSE_API}")
            # Temporary sleep to allow UI elements to be displayed before this blocking code runs
            QApplication.processEvents()
            time.sleep(0.1)
            response = requests.post(f"{ENDPOINT}/{PARSE_API}", files=files)
            print(f"[DEBUG] Server response status: {response.status_code}")
            data = response.json()
            print(f"[DEBUG] Server response data: {json.dumps(data, indent=2)}")
            parsed_content_list = data["parsed_content_list"]
            parsed_content_list = '\n'.join([f'type: {x["type"]}, content: {x["content"]}, interactivity: {x["interactivity"]}' for x in parsed_content_list])
            self.text_area.setText(parsed_content_list)
            self.__toggleProgressBar()
            
            # Download and display labeled image if available
            if 'labeled_image_path' in data:
                print("[DEBUG] Labeled image path found in response")
                self.download_and_display_labeled_image(data)    
        except Exception as e:
            print(f"[ERROR] Failed to send request: {str(e)}")
            print(f"[ERROR] Exception type: {type(e)}")
            import traceback
            print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            self.text_area.append(f"\nError sending to server: {str(e)}")



    def download_and_display_labeled_image(self, json_response):
        print("\n[DEBUG] download_and_display_labeled_image: Starting download")
        try:
            labeled_image_path = json_response['labeled_image_path']
            print(f"[DEBUG] Downloading image from: {ENDPOINT}/{labeled_image_path}")
            response = requests.get(f"{ENDPOINT}/{labeled_image_path}")
            print(f"[DEBUG] Download response status: {response.status_code}")
            image_name = os.path.basename(labeled_image_path)
            downloaded_image_path = os.path.join(SCREENSHOT_DIR, image_name)
            with open(downloaded_image_path, 'wb') as f:
                f.write(response.content)
            print("[DEBUG] Labeled image downloaded successfully")
            self.display_image(downloaded_image_path)
        except Exception as e:
            print(f"[ERROR] Failed to download/display labeled image: {str(e)}")
            print(f"[ERROR] Exception type: {type(e)}")
            import traceback
            print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            self.text_area.append(f"\nError downloading labeled image: {str(e)}")

    def __toggleProgressBar(self):
        if not hasattr(self, 'progress_bar') or not self.progress_bar:
            self.progress_bar = QProgressBar(self)
            self.text_area.setText("Loading...")
            self.progress_bar = QProgressBar(self)
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setValue(0)
            self.progress_bar.setFixedSize(200, 20)
            self.progress_bar.show()
            self.layout.addWidget(self.progress_bar)
            QApplication.processEvents()  # Process any pending events
        else:
            self.layout.removeWidget(self.progress_bar) 
            self.progress_bar = None





def main():
    app = QApplication(sys.argv)
    window = ScreenshotApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()