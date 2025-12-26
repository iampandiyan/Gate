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

        # 1. Preprocess for RT-DETR
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)

        # 2. Inference
        with torch.no_grad():
            outputs = self.model(**inputs)

        # 3. Post-process (Filter low confidence)
        target_sizes = torch.tensor([pil_img.size[::-1]]).to(self.device)
        results = self.processor.post_process_object_detection(outputs, target_sizes=target_sizes, threshold=0.5)[0]

        # Screen dimensions for Position Filter
        frame_h, frame_w, _ = frame.shape
        center_x_min = frame_w * 0.20  # Left boundary (20%)
        center_x_max = frame_w * 0.80  # Right boundary (80%)

        # 4. Loop through detections
        for score, label, box in zip(results["scores"], results["labels"], results["boxes"]):
            if score < 0.5: continue
            
            # Extract coordinates
            box = [round(i, 2) for i in box.tolist()]
            x, y, x2, y2 = map(int, box)
            
            # Boundary Checks (ensure within frame)
            x, y = max(0, x), max(0, y)
            x2, y2 = min(frame_w, x2), min(frame_h, y2)
            
            # --- FILTER 1: Aspect Ratio & Size ---
            w_box = x2 - x
            h_box = y2 - y
            if w_box == 0 or h_box == 0: continue
            
            area = w_box * h_box
            aspect_ratio = w_box / h_box
            
            # Reject if too small (far away)
            if area < 3000: 
                # print(f"Skipping: Too small (Area: {area})")
                continue
            
            # Reject if weird shape (Indian plates are approx 2.0 to 4.5 ratio)
            # We allow 1.5 to 6.0 to be safe
            if aspect_ratio < 1.5 or aspect_ratio > 6.0:
                # print(f"Skipping: Bad shape (Ratio: {aspect_ratio:.2f})")
                continue

            # --- FILTER 2: Center Screen Check ---
            plate_center_x = x + (w_box / 2)
            # Only process if plate is mostly in the center zone
            if not (center_x_min < plate_center_x < center_x_max):
                # print("Skipping: Plate on edge")
                continue

            # Crop Plate
            plate_crop = frame[y:y2, x:x2]
            if plate_crop.size == 0: continue

            # --- FILTER 3: Blur Detection ---
            # Using Laplacian Variance to detect motion blur
            gray_plate = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.Laplacian(gray_plate, cv2.CV_64F).var()
            
            # Threshold: < 100 is usually blurry. 
            if blur_score < 80: 
                # print(f"Skipping: Too blurry (Score: {blur_score:.1f})")
                continue
            
            # === PASSED ALL CHECKS -> RUN OCR ===
            print(f"⚡ Processing Plate (Conf: {score:.2f} | Blur: {blur_score:.0f})")

            # A. Upscale for better OCR
            scale = 2.0
            enhanced = cv2.resize(plate_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
            # B. Run EasyOCR
            # Returns: [(bbox, text, prob), ...]
            ocr_results = self.reader.readtext(enhanced)
            
            # C. Collect Valid Segments
            valid_segments = []
            for (bbox, text, prob) in ocr_results:
                if prob > 0.3: # Filter garbage reads
                    x_start = bbox[0][0]
                    valid_segments.append((x_start, text, prob))

            # D. CRITICAL: SORT LEFT-TO-RIGHT
            # This fixes "01 MH" -> "MH 01" issue
            valid_segments.sort(key=lambda x: x[0])

            # E. Join and Clean
            full_text = "".join([seg[1] for seg in valid_segments])
            clean_text = re.sub(r'[^A-Z0-9]', '', full_text.upper())
            
            # F. Final Check
            if len(clean_text) > 4:
                return clean_text, score.item(), plate_crop

        return None, 0, None


