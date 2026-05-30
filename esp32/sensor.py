import json
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
import requests

BASE_DIR = Path(__file__).resolve().parent.parent

from esp32.motor import handle_classification_result
from esp32.database import db

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/sensor"
MQTT_RESULT_TOPIC = "esp32/result"
AI_PREDICT_URL = "http://127.0.0.1:8010/predict"

CAM_URL = "http://192.168.137.240/capture"

LATEST_CAPTURE_PATH = BASE_DIR / "captured_image.jpg"
PHOTO_DATA_DIR = BASE_DIR / "photoData"

# ESP32-CAM에서 정지 이미지를 받아 로컬에 저장한다.
def fetch_still_image() -> Path | None:
	for attempt in range(1, 4):
		try:
			capture_url = f"{CAM_URL}?t={int(time.time() * 1000)}"
			response = requests.get(capture_url, timeout=12, headers={"Connection": "close"})
			if response.status_code != 200 or not response.content:
				time.sleep(0.5)
				continue

			PHOTO_DATA_DIR.mkdir(parents=True, exist_ok=True)
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			photo_data_path = PHOTO_DATA_DIR / f"capture_{timestamp}.jpg"
			LATEST_CAPTURE_PATH.write_bytes(response.content)
			photo_data_path.write_bytes(response.content)

			return photo_data_path
		except Exception:
			time.sleep(0.5)
	return None

# 캡처 이미지를 분류하고 모터 제어 토픽으로 전달한다.
def classify_and_forward(image_path: Path) -> int:
	result = classify_with_ai_service(image_path)
	handle_classification_result(result)
	return result


# AI 추론 서버에 이미지 경로를 전달해 분류값을 받는다.
def classify_with_ai_service(image_path: Path) -> int:
	try:
		response = requests.post(
			AI_PREDICT_URL,
			json={"image_path": str(image_path)},
			timeout=20,
		)
		if response.status_code != 200:
			return 0
		data = response.json()
		return int(data.get("result", 0))
	except Exception:
		return 0


# MQTT 연결 성공 시 센서 토픽 구독을 시작한다.
def on_connect(client, userdata, flags, rc):
	if rc == 0:
		client.subscribe(MQTT_TOPIC)


# 센서 메시지를 처리해 캡처/분류/결과저장을 수행한다.
def on_message(client, userdata, msg):
	payload_str = msg.payload.decode("utf-8").strip()
	try:
		payload = json.loads(payload_str)
	except json.JSONDecodeError:
		payload = {"signal": int(payload_str) if payload_str.isdigit() else 0}

	signal = int(payload.get("signal", 0))
	random_key = str(payload.get("random_key", "")).strip()

	if signal != 1:
		return

	image_path = fetch_still_image()
	if image_path is None:
		return

	result = classify_and_forward(image_path)

	result_payload = {
		"random_key": random_key,
		"result": result,
		"processed_at": datetime.utcnow().isoformat(timespec="seconds"),
	}
	client.publish(MQTT_RESULT_TOPIC, json.dumps(result_payload, ensure_ascii=False), qos=1)

	if not random_key:
		return

	try:
		db.save_result_sync(
			random_key=random_key,
			result_value=result,
			sensor_payload=payload,
			image_path=str(image_path),
		)
	except Exception:
		return


# MQTT 센서 구독기를 실행한다.
def main() -> None:
	client = mqtt.Client()
	client.username_pw_set("admin", "qwer1234")
	client.on_connect = on_connect
	client.on_message = on_message

	client.connect(MQTT_HOST, MQTT_PORT, 60)
	client.loop_forever()


if __name__ == "__main__":
	main()
