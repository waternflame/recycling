import os
from pathlib import Path
import torch
import torch.nn as nn
import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm
import shutil

# GPU 확인
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = str(BASE_DIR / 'can_pet_model.pth')
loaded_model = None

# ============================================
# 1. CNN 모델 정의
# ============================================
class CanPetCNN(nn.Module):
    def __init__(self):
        super(CanPetCNN, self).__init__()
        
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool2d(2, 2)
        
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool2d(2, 2)
        
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.pool3 = nn.MaxPool2d(2, 2)
        
        self.fc1 = nn.Linear(128 * 8 * 8, 128)
        self.dropout = nn.Dropout(0.5)
        self.fc2 = nn.Linear(128, 1)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        x = self.relu(self.conv1(x))
        x = self.pool1(x)
        
        x = self.relu(self.conv2(x))
        x = self.pool2(x)
        
        x = self.relu(self.conv3(x))
        x = self.pool3(x)
        
        x = x.view(x.size(0), -1)
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.sigmoid(self.fc2(x))
        
        return x

# ============================================
# 2. 모델 로드
# ============================================
def load_model(model_path):
    model = CanPetCNN().to(device)
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        return model
    except FileNotFoundError:
        return None


def get_model():
    global loaded_model
    if loaded_model is None:
        if not os.path.exists(MODEL_PATH):
            return None

        loaded_model = CanPetCNN().to(device)
        loaded_model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        loaded_model.eval()
    return loaded_model

# ============================================
# 3. 이미지 전처리 (흑백만)
# ============================================
def preprocess_image_for_test(img_path):
    """
    이미지를 흑백으로만 전처리
    """
    try:
        img = Image.open(img_path).convert('L')
        img_array = np.array(img)
    except Exception as e:
        return None
    
    # 64x64 리사이징
    img_resized = cv2.resize(img_array, (64, 64))
    
    # 정규화 및 형태 변환
    input_data = torch.FloatTensor(img_resized).reshape(1, 1, 64, 64) / 255.0
    
    return input_data.to(device)

# ============================================
# 4. 추론 함수
# ============================================
def classify_image(model, img_path, confidence_threshold=0.5):
    """
    이미지 분류
    confidence_threshold 이상: 확실하게 분류
    그 이하: 불확실한 것으로 간주 (0 반환)
    """
    input_data = preprocess_image_for_test(img_path)
    
    if input_data is None:
        return 0, 0.0  # 읽기 실패 -> unknown(0)
    
    with torch.no_grad():
        output = model(input_data)
    
    confidence = float(output[0][0].cpu().numpy())
    
    # 분류 결정
    if confidence < 0.5:
        # 캔에 가까움 -> 서비스 코드 1
        confidence_diff = 0.5 - confidence
        if confidence_diff > (1 - confidence_threshold):
            return 1, confidence_diff
        else:
            return 0, confidence_diff
    else:
        # 패트에 가까움 -> 서비스 코드 2
        confidence_diff = confidence - 0.5
        if confidence_diff > (1 - confidence_threshold):
            return 2, confidence_diff
        else:
            return 0, confidence_diff


def predict_now(img_path):
    model = get_model()
    if model is None:
        return 0

    label, confidence = classify_image(model, img_path, confidence_threshold=0.7)

    return int(label)


def analyze_image_for_motor(img_path: str) -> int:
    if not os.path.exists(img_path):
        return 0
    return predict_now(img_path)


