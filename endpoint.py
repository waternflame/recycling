from fastapi import FastAPI, File, UploadFile, Form
import cv2
import numpy as np
import os
import time
import database
import test

app = FastAPI()

# 1. 크롭된 이미지를 저장할 폴더 설정
CROP_DIR = "testset"
os.makedirs(CROP_DIR, exist_ok=True)
database.init_db()

@app.post("/upload")
async def upload_data(sensor_pos: int = Form(...), file: UploadFile = File(...)):
    # 파일 수신 (메모리에서 바로 이미지로 변환)
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"result": 2, "msg": "fail to read image"}

    # 2. 이미지 로직 (센서 위치에 따른 Crop)
    h, w = img.shape[:2]
    unit = h // 3

    if sensor_pos == 1:
        roi = img[0:unit, :]
    elif sensor_pos == 2:
        roi = img[unit:unit*2, :]
    elif sensor_pos == 3:
        roi = img[unit*2:h, :]
    else:
        roi = img[unit:unit*2, :]

    # 3. crop된 이미지를 그대로 testset에 저장
    # 4. image 폴더에 파일 하나씩 저장
    # 파일명이 겹치지 않게 타임스탬프를 사용합니다.
    file_name = f"crop_{int(time.time() * 1000)}.jpg"
    save_path = os.path.join(CROP_DIR, file_name)
    saved = cv2.imwrite(save_path, roi)
    if not saved:
        return {"result": 2, "msg": "fail to save cropped image"}

    result = test.predict_now(save_path)

    print(f"cropped image saved: {save_path} | result: {result}")

    # 5. ESP32-CAM 응답
    return {
        "result": result,
        "msg": "cropped image saved and analyzed",
        "file_path": save_path
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
