import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import cv2
import os
from sklearn.model_selection import train_test_split
from PIL import Image

# GPU 사용 가능 여부 확인
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"사용 디바이스: {device}\n")

# ============================================
# 1. CNN 모델 정의
# ============================================
class CanPetCNN(nn.Module):
    def __init__(self):
        super(CanPetCNN, self).__init__()
        
        # 합성곱 층
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.pool1 = nn.MaxPool2d(2, 2)
        
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.pool2 = nn.MaxPool2d(2, 2)
        
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.pool3 = nn.MaxPool2d(2, 2)
        
        # 완전 연결층
        self.fc1 = nn.Linear(128 * 8 * 8, 128)
        self.dropout = nn.Dropout(0.5)
        self.fc2 = nn.Linear(128, 1)
        
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        # Conv Block 1
        x = self.relu(self.conv1(x))
        x = self.pool1(x)
        
        # Conv Block 2
        x = self.relu(self.conv2(x))
        x = self.pool2(x)
        
        # Conv Block 3
        x = self.relu(self.conv3(x))
        x = self.pool3(x)
        
        # Flatten & FC
        x = x.view(x.size(0), -1)
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.sigmoid(self.fc2(x))
        
        return x

# ============================================
# 2. 이미지 전처리 함수
# ============================================
def preprocess_image(img_path):
    """
    이미지를 흑백으로 변환하고 엣지 감지
    캔: 둥근 곡선, 패트: 직선
    """
    try:
        # PIL로 이미지 열기 (한글 파일명 지원)
        img = Image.open(img_path).convert('L')
        img_array = np.array(img)
    except Exception as e:
        print(f"❌ 파일 읽기 실패: {os.path.basename(img_path)}")
        return None
    
    # 64x64 리사이징
    img_resized = cv2.resize(img_array, (64, 64))
    
    # 노이즈 제거
    img_blurred = cv2.GaussianBlur(img_resized, (5, 5), 0)
    
    # Canny 엣지 감지
    edges = cv2.Canny(img_blurred, 30, 100)
    
    return edges

# ============================================
# 3. PyTorch Dataset 클래스
# ============================================
class CanPetDataset(Dataset):
    def __init__(self, images, labels):
        self.images = torch.FloatTensor(images)
        self.labels = torch.FloatTensor(labels)
    
    def __len__(self):
        return len(self.images)
    
    def __getitem__(self, idx):
        return self.images[idx], self.labels[idx]

# ============================================
# 4. 데이터 로드 및 전처리
# ============================================
def load_data(base_path):
    """
    폴더에서 이미지 로드
    dataset/0/ → 캔 (label=0)
    dataset/1/ → 패트 (label=1)
    """
    images = []
    labels = []
    
    for label in [0, 1]:
        folder_path = os.path.join(base_path, str(label))
        
        if not os.path.exists(folder_path):
            print(f"⚠️  폴더 없음: {folder_path}")
            continue
        
        count = 0
        for filename in os.listdir(folder_path):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                continue
            
            filepath = os.path.join(folder_path, filename)
            edges = preprocess_image(filepath)
            
            if edges is not None:
                images.append(edges)
                labels.append(label)
                count += 1
        
        label_name = "캔" if label == 0 else "패트"
        print(f"✅ {label_name}({label}): {count}장 로드됨")
    
    if len(images) == 0:
        return None, None
    
    # 정규화 및 형태 변환
    X = np.array(images).reshape(-1, 1, 64, 64) / 255.0
    y = np.array(labels, dtype=np.float32).reshape(-1, 1)
    
    return X, y

# ============================================
# 5. 학습 함수
# ============================================
def train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=20):
    """
    모델 학습
    """
    for epoch in range(num_epochs):
        # ---- 훈련 ----
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            
            # Forward
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            # Backward
            loss.backward()
            optimizer.step()
            
            # 통계
            train_loss += loss.item()
            predictions = (outputs > 0.5).float()
            train_correct += (predictions == labels).sum().item()
            train_total += labels.size(0)
        
        train_loss /= len(train_loader)
        train_acc = (train_correct / train_total) * 100
        
        # ---- 검증 ----
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                predictions = (outputs > 0.5).float()
                val_correct += (predictions == labels).sum().item()
                val_total += labels.size(0)
        
        val_loss /= len(val_loader)
        val_acc = (val_correct / val_total) * 100
        
        # 로그
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1:2d}/{num_epochs}] | "
                  f"Train Loss: {train_loss:.4f} Acc: {train_acc:.1f}% | "
                  f"Val Loss: {val_loss:.4f} Acc: {val_acc:.1f}%")

# ============================================
# 6. 메인 실행
# ============================================
if __name__ == "__main__":
    DATASET_PATH = r"d:\python\dataset"
    
    print("=" * 60)
    print("🤖 캔 vs 패트 분류 모델 - PyTorch")
    print("=" * 60)
    print(f"\n📂 데이터셋 경로: {DATASET_PATH}\n")
    
    # 데이터 로드
    print("📥 데이터 로드 중...\n")
    X_train, y_train = load_data(DATASET_PATH)
    
    if X_train is None:
        print("\n❌ 에러: 데이터가 없습니다!")
        print(f"   {DATASET_PATH}/0/ 과 /1/ 폴더를 만들고 사진을 넣으세요.\n")
        exit()
    
    print(f"\n✅ 총 {len(X_train)}장 로드됨")
    y_flat = y_train.flatten()
    print(f"   캔(0): {int(sum(y_flat == 0))}장")
    print(f"   패트(1): {int(sum(y_flat == 1))}장\n")
    
    # 훈련/검증 분할
    X_train_split, X_val, y_train_split, y_val = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42
    )
    
    # Dataset & DataLoader
    train_dataset = CanPetDataset(X_train_split, y_train_split)
    val_dataset = CanPetDataset(X_val, y_val)
    
    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
    
    # 모델 생성
    model = CanPetCNN().to(device)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    print("📊 모델 구조:")
    print(model)
    print()
    
    # 학습 시작
    print("🚀 학습 시작...\n")
    train_model(model, train_loader, val_loader, criterion, optimizer, num_epochs=20)
    
    # 모델 저장
    torch.save(model.state_dict(), 'can_pet_model.pth')
    
    print("\n" + "=" * 60)
    print("✅ 학습 완료! 모델을 'can_pet_model.pth'로 저장했습니다.")
    print("=" * 60)
