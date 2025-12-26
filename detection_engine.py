import torch
import cv2
import easyocr
import re
import numpy as np
from PIL import Image
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

class AIEngine:
    def __init__(self, model_path="./models/rtdetr_best"):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🚀 AI Engine loading on: {self.device}")
        
        # 1. Load RT-DETR
        try:
            self.processor = RTDetrImageProcessor.from_pretrained(model_path)
            self.model = RTDetrForObjectDetection.from_pretrained(model_path).to(self.device)
            print("✅ Custom RT-DETR Model Loaded")
        except Exception as e:
            print(f"❌ Failed to load RT-DETR: {e}")
            self.model = None

        # 2. Load EasyOCR
        # 'en' is usually sufficient for Indian plates (A-Z, 0-9)
        self.reader = easyocr.Reader(['en'], gpu=(self.device == 'cuda'))
        print("✅ EasyOCR Loaded")

    def detect_and_read(self, frame):
        """
        Returns: (detected_text, confidence, cropped_plate_image)
        """
        if self.model is None: return None, 0, None

        # A. Preprocess for RT-DETR
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)

        # B. Inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # C. Post-process (Filter low confidence)
        target_sizes = torch.tensor([pil_img.size[::-1]]).to(self.device)
        results = self.processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.5)[0]

        best_text = None
        best_conf = 0.0
        best_crop = None

        # D. Loop through detections (usually just 1 plate)
        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            if score < 0.5: continue
            
            # Extract coordinates
            box = [round(i, 2) for i in box.tolist()]
            x, y, x2, y2 = map(int, box)
            
            # Crop Plate
            h, w, _ = frame.shape
            x, y = max(0, x), max(0, y)
            x2, y2 = min(w, x2), min(h, y2)
            
            plate_crop = frame[y:y2, x:x2]
            if plate_crop.size == 0: continue

            # E. Run OCR on the Crop
            # Optional: Upscale crop for better OCR
            scale = 2.0
            enhanced = cv2.resize(plate_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
            ocr_result = self.reader.readtext(enhanced)
            
            # Join text chunks (e.g., "TN", "05", "AA", "1234")
            full_text = "".join([res[1] for res in ocr_result])
            
            # F. Clean Text (Remove special chars, only A-Z and 0-9)
            clean_text = re.sub(r'[^A-Z0-9]', '', full_text.upper())
            
            if len(clean_text) > 4: # Minimum length for a valid plate
                return clean_text, score.item(), plate_crop

        return None, 0, None
