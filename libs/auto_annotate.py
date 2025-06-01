# libs/auto_annotate.py
import os
import torch
from ultralytics import YOLO
from pathlib import Path

class YOLOAutoAnnotator:
    def __init__(self, model_dir='yolo_model', class_list=None, conf_threshold=0.25):
        self._ensure_model_directory(model_dir)
        self.model_path = self._find_model_file(model_dir)
        if not self.model_path:
            raise FileNotFoundError(f"No .pt model file found in '{model_dir}' directory.")
        self.model = YOLO(self.model_path)
        self.class_list = class_list if class_list else self.model.names
        self.conf_threshold = conf_threshold

    def _ensure_model_directory(self, model_dir):
        model_dir_path = Path(model_dir)
        if not model_dir_path.exists():
            model_dir_path.mkdir(parents=True, exist_ok=True)

    def _find_model_file(self, model_dir):
        model_dir_path = Path(model_dir)
        pt_files = sorted(model_dir_path.glob("*.pt"))
        return str(pt_files[0]) if pt_files else None

    def annotate(self, image_path):
        results = self.model(image_path)[0]
        annotations = []
        for box in results.boxes.data.tolist():
            x1, y1, x2, y2, conf, cls = box
            if conf < self.conf_threshold:
                continue
            label = self.class_list[int(cls)]
            rect = [int(x1), int(y1), int(x2), int(y2)]
            annotations.append({'label': label, 'bbox': rect, 'confidence': conf})
        return annotations
