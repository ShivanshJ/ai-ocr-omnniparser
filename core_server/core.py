from PIL import Image
import torch
from typing import Tuple, Dict, List, Any, Optional
import base64
from pathlib import Path

from OmniParser.utils import (
    get_yolo_model,
    get_caption_model_processor,
    get_som_labeled_img,
    check_ocr_box
)
from .constants import IMAGE_BASE_PATH, RESULT_IMG_FOLDER_NAME, ICON_CAPTION_MODEL_PATH

class ImageProcessor:

    def __init__(
        self,
        icon_detect_model_path: str,
        icon_caption_model_name: str = "florence2",
        icon_caption_model_path: str = str(Path(__file__).parent.parent / ICON_CAPTION_MODEL_PATH),
        device: Optional[torch.device] = None
    ):
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.icon_detect_model = get_yolo_model(icon_detect_model_path)
        self.icon_caption_model = get_caption_model_processor(
            model_name=icon_caption_model_name,
            model_name_or_path=icon_caption_model_path
        )

    def process_image(
        self,
        image_path: str,
        result_image_name: str,
        box_threshold: float = 0.01,
        iou_threshold: float = 0.9,
        use_paddleocr: bool = False,
        imgsz: int = 640,
        icon_process_batch_size: int = 32
    ) -> Tuple[str, Dict[str, Any], List[Any]]:
        """
        Process an image through OCR and SOM model pipeline
        
        Args:
            image_path: Path to the input image
            box_threshold: Confidence threshold for box detection
            iou_threshold: IOU threshold for box merging
            use_paddleocr: Whether to use PaddleOCR instead of EasyOCR
            imgsz: Input image size for the model
            icon_process_batch_size: Batch size for icon processing
            
        Returns:
            Tuple containing:
            - Base64 encoded labeled image
            - Dictionary of label coordinates
            - List of parsed content
        """
        # Get OCR results
        ocr_bbox_rslt, _ = check_ocr_box(
            image_path,
            display_img=False,
            output_bb_format='xyxy',
            easyocr_args={'paragraph': False, 'text_threshold': 0.9},
            use_paddleocr=use_paddleocr
        )
        ocr_text, ocr_bbox = ocr_bbox_rslt
        print ('OCR done')

        # Process with SOM model
        dino_labeled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image_path,
            model=self.icon_detect_model,
            BOX_TRESHOLD=box_threshold,
            iou_threshold=iou_threshold,
            caption_model_processor=self.icon_caption_model,
            ocr_bbox=ocr_bbox,
            ocr_text=ocr_text,
            imgsz=imgsz,
            batch_size=icon_process_batch_size
        )
        print ('Image processed')
        # Save image locally
        self.__save_labeled_image(dino_labeled_img, result_image_name)
        print ('Image saved')

        return dino_labeled_img, label_coordinates, parsed_content_list


    def __save_labeled_image(self, dino_labeled_img: str, file_name: str) -> None:
        labeled_img_path = f"{IMAGE_BASE_PATH}/{RESULT_IMG_FOLDER_NAME}/{file_name}"
        with open(labeled_img_path, "wb") as f:
            f.write(base64.b64decode(dino_labeled_img))
        