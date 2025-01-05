from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import io
from PIL import Image
import base64
import uuid
from pathlib import Path

from .core import ImageProcessor
from .constants import IMAGE_BASE_PATH, UPLOAD_IMG_FOLDER_NAME, ICON_DETECT_MODEL_PATH

app = FastAPI(title="OmniParser API")


# Initialize image processor
IMAGE_PROCESSOR = ImageProcessor(
    icon_detect_model_path=str(Path(__file__).parent.parent / ICON_DETECT_MODEL_PATH)
)


@app.post("/parse-screenshot")
async def parse_screenshot(
    file: UploadFile = File(...),
    box_threshold: float = 0.01,
    iou_threshold: float = 0.9,
    use_paddleocr: bool = False,
    imgsz: int = 640,
    icon_process_batch_size: int = 32
):
    try:
        # Read and save the uploaded image
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes))
        
        # Step1: Save image temporarily
        image_uuid = uuid.uuid4().hex[:5]
        file_name = ''.join(file.filename.split('.')[:-1])
        print (file.filename, file_name)
        temp_path = f"{IMAGE_BASE_PATH}/{UPLOAD_IMG_FOLDER_NAME}/{image_uuid}-{file.filename}"
        image.save(temp_path)
        print ('Save imaged temporarily')

        # Step2, Process the image using the ImageProcessor
        result_image_name = f"{image_uuid}-labeled_img-{file.filename}"
        dino_labeled_img, label_coordinates, parsed_content_list = IMAGE_PROCESSOR.process_image(
            image_path=temp_path,
            result_image_name=result_image_name,
            box_threshold=box_threshold,
            iou_threshold=iou_threshold,
            use_paddleocr=use_paddleocr,
            imgsz=imgsz,
            icon_process_batch_size=icon_process_batch_size,
        )
        print ('Image processed & Saved')
        
        # Step3: Return results
        return JSONResponse({
            "labeled_image_path": f"static/{result_image_name}",
            "label_coordinates": {k: v.tolist() if hasattr(v, 'tolist') else v for k, v in label_coordinates.items()},
            "parsed_content_list": parsed_content_list
        })
        
    except Exception as e:
        print (str(e))
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
