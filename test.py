import torch
import torch.nn as nn
import cv2
import numpy as np
import os
from PIL import Image
from tqdm import tqdm
import database
import shutil

# GPU 확인
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"사용 디바이스: {device}\n")
MODEL_PATH = 'can_pet_model.pth'
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
        print(f"✅ 모델 로드 성공: {model_path}\n")
        return model
    except FileNotFoundError:
        print(f"❌ 모델을 찾을 수 없습니다: {model_path}")
        return None


def get_model():
    global loaded_model
    if loaded_model is None:
        if not os.path.exists(MODEL_PATH):
            print(f"❌ 모델을 찾을 수 없습니다: {MODEL_PATH}")
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
    그 이하: 불확실한 것으로 간주 (2 반환)
    """
    input_data = preprocess_image_for_test(img_path)
    
    if input_data is None:
        return 2, 0.0  # 읽기 실패 → 2
    
    with torch.no_grad():
        output = model(input_data)
    
    confidence = float(output[0][0].cpu().numpy())
    
    # 분류 결정
    if confidence < 0.5:
        # 캔(0)에 가까움
        confidence_diff = 0.5 - confidence
        if confidence_diff > (1 - confidence_threshold):
            return 0, confidence_diff
        else:
            return 2, confidence_diff
    else:
        # 패트(1)에 가까움
        confidence_diff = confidence - 0.5
        if confidence_diff > (1 - confidence_threshold):
            return 1, confidence_diff
        else:
            return 2, confidence_diff


def predict_now(img_path):
    model = get_model()
    if model is None:
        return 2

    label, confidence = classify_image(model, img_path, confidence_threshold=0.7)

    # API 경로에서 바로 호출될 때를 대비해 테이블 존재를 보장
    database.init_db()

    database.save_results([{'file_path': img_path, 'label': label}])

    return int(label)

# ============================================
# 5. 메인 실행 (분류만 수행, 저장 안함)
# ============================================
if __name__ == "__main__":
    # 설정
    TEST_FOLDER = r"d:\python\testset"  # 테스트할 사진 폴더
    CONFIDENCE_THRESHOLD = 0.7  # 신뢰도 임계값

    database.init_db()
    
    print("=" * 60)
    print("🔍 이미지 분류 시작")
    print("=" * 60)
    print(f"\n📂 입력 폴더: {TEST_FOLDER}")
    print(f"⚙️  신뢰도 임계값: {CONFIDENCE_THRESHOLD}\n")
    
    # 모델 로드
    model = load_model(MODEL_PATH)
    if model is None:
        exit()
    
    # 테스트 폴더 확인
    if not os.path.exists(TEST_FOLDER):
        print(f"❌ 폴더가 없습니다: {TEST_FOLDER}")
        exit()
    
    # 이미지 파일 목록
    image_files = []
    for filename in os.listdir(TEST_FOLDER):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
            image_files.append(filename)
    
    if len(image_files) == 0:
        print(f"❌ 이미지 파일이 없습니다: {TEST_FOLDER}")
        exit()
    
    # 첫 번째 이미지만 선택
    image_files = image_files[:1]
    
    print(f"📊 {image_files[0]} 처리 중...\n")
    
    # 분류 결과 저장 (딕셔너리)
    results = []
    
    # 이미지 분류 (첫 번째만)
    for filename in image_files:
        img_path = os.path.join(TEST_FOLDER, filename)
        label, confidence = classify_image(model, img_path, CONFIDENCE_THRESHOLD)

        database.save_results([{'file_path': img_path, 'label': label}])

        results.append({
            'file_path': img_path,
            'filename': filename,
            'label': label,
            'confidence': confidence
        })
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("✅ 분류 완료!")
    print("=" * 60)
    
    result = results[0]
    label_names = {0: "🥫 캔", 1: "🥤 패트", 2: "❓ 불확실"}
    
    
    print(f"\n📷 파일: {result['filename']}")
    print(f"📂 경로: {result['file_path']}")
    print(f"🏷️  결과: {label_names[result['label']]}")
    print(f"🔢 반환된 정수값: {result['label']}") 
    print(f"📊 신뢰도: {result['confidence']:.2f}\n")
    print(f"💾 결과 데이터: {result}")


    print(f"✅ DB 저장 완료: {result['filename']} -> {result['label']}")

