# YOLOv7 for Bone Fractures Detection

Trained YOLOv7 for bone fracture detections.

[![python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![pytorch](https://img.shields.io/badge/PyTorch-1.13.1-EE4C2C.svg?style=flat&logo=pytorch)](https://pytorch.org)
[![Docker pulls](https://img.shields.io/docker/pulls/mdciri/bone-fracture-detection)](https://hub.docker.com/repository/docker/mdciri/bone-fracture-detection)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.13.0-FF4B4B.svg?style=flat&logo=Streamlit&logoColor=white)](https://streamlit.io)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Data
The [GRAZPEDWRI-DX](https://www.nature.com/articles/s41597-022-01328-z) is an open dataset containing 20,327 annotated pediatric trauma wrist radiograph images of 6,091 patients, treated at the Department for Pediatric Surgery of the University Hospital Graz between 2008 and 2018. Several pediatric radiologists annotated the images by placing bounding boxes to mark 9 different classes:

- `boneanomaly` (276 boxes)
- `bonelesion` (45 boxes)
- `foreignbody` (8 boxes)
- `fracture` (18,090 boxes)
- `metal` (818 boxes)
- `periostealreaction` (3,453 boxes)
- `pronatorsign` (567 boxes)
- `softtissue` (464 boxes)
- `text` (23,722 boxes)

The data are already annotated in many different formats, one of them is YOLO. This project uses a trained YOLOv7-p6 model for inference.

---

## Quick Start for Windows

### 1) Clone and enter the repo
```powershell
git clone https://github.com/mdciri/YOLOv7-Bone-Fracture-Detection.git
cd YOLOv7-Bone-Fracture-Detection
```

### 2) Create a Python virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies
```powershell
python -m pip install --upgrade pip
pip install -r app/requirements-docker.txt
# Optional: for the desktop GUI
pip install PySide6
```

### 4) Download the ONNX model (place it in repo root)
```powershell
Invoke-WebRequest -Uri "https://github.com/mdciri/YOLOv7-Bone-Fracture-Detection/releases/download/trained-models/yolov7-p6-bonefracture.onnx" -OutFile "yolov7-p6-bonefracture.onnx"
```

### 5) Run the Streamlit WebApp
```powershell
streamlit run app/webapp.py
```
- Open the URL shown (usually `http://localhost:8501`).

---

## Optional: Desktop GUI (PySide6)
```powershell
python gui/gui.py
```

---

## Optional: ONNX CLI inference
```powershell
python inference_onnx.py `
  --model-path .\yolov7-p6-bonefracture.onnx `
  --img-path .\GRAZPEDWRI-DX_dataset\images\test\some_image.png `
  --dst-path .\predictions `
  --device cpu
```

---

## Docker
```powershell
docker pull mdciri/bone-fracture-detection:latest
docker run -p 8501:8501 mdciri/bone-fracture-detection
```

---

## Training / Evaluation (advanced)

The PyTorch model (`yolov7-p6-bonefracture.pt`) is also available. To evaluate or perform inference using the original YOLOv7 repo scripts, place the model in a YOLOv7 clone and use `test.py` / `detect.py`. To train from scratch, use `train.py`.

---

## Results
Evaluation results are stored in the `runs/test` folder, including predicted labels, confusion matrix, F1, precision, recall, and PR curve plots.

---

## License
GNU General Public License v3.0, same as the YOLOv7 license.

---

## References
- [A pediatric wrist trauma X-ray dataset (GRAZPEDWRI-DX) for machine learning](https://www.nature.com/articles/s41597-022-01328-z)
- [YOLOv7: Trainable bag-of-freebies sets new state-of-the-art for real-time object detectors](https://arxiv.org/abs/2207.02696)

