import base64
import json
import os
import time
from datetime import datetime

import paho.mqtt.client as mqtt

import test

# Broker settings
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "qwer1234")

# Topic mapping
TOPIC3_IMAGE = os.getenv("TOPIC3_IMAGE", "topic3")
TOPIC1_RESULT = os.getenv("TOPIC1_RESULT", "topic1")

# Where incoming camera images are stored
SAVE_DIR = os.getenv("CAPTURE_SAVE_DIR", "testset")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _save_raw_jpeg(binary_data: bytes) -> str:
    _ensure_dir(SAVE_DIR)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_path = os.path.join(SAVE_DIR, f"capture_{ts}.jpg")
    with open(file_path, "wb") as f:
        f.write(binary_data)
    return file_path


def _decode_payload(payload: bytes) -> bytes:
    """
    Supports:
    - raw JPEG bytes from ESP32-CAM
    - JSON with base64 image, e.g. {"image":"..."} or {"image_b64":"..."}
    """
    try:
        text = payload.decode("utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            b64 = data.get("image") or data.get("image_b64")
            if b64:
                return base64.b64decode(b64)
    except Exception:
        pass

    return payload


def _run_ai_pipeline(image_path: str) -> int:
    # Use test.py directly so the runtime flow stays within topic1/topic2/test files.
    label = test.predict_now(image_path)
    return int(label)


def on_connect(client: mqtt.Client, userdata, flags, rc):
    if rc == 0:
        print("[OK] MQTT broker connected")
        client.subscribe(TOPIC3_IMAGE, qos=1)
        print(f"[SUB] {TOPIC3_IMAGE}")
    else:
        print(f"[ERROR] MQTT connect failed rc={rc}")


def on_message(client: mqtt.Client, userdata, msg):
    if msg.topic != TOPIC3_IMAGE:
        return

    print(f"[RECV] {TOPIC3_IMAGE} payload_size={len(msg.payload)}")
    try:
        image_bytes = _decode_payload(msg.payload)
        image_path = _save_raw_jpeg(image_bytes)
        print(f"[SAVE] {image_path}")

        label = _run_ai_pipeline(image_path)
        payload = {
            "label": label,
            "file_path": image_path,
            "ts": int(time.time()),
        }
        client.publish(TOPIC1_RESULT, json.dumps(payload), qos=1)
        print(f"[PUB] {TOPIC1_RESULT} <- {payload}")
    except Exception as e:
        print(f"[ERROR] processing failed: {e}")


def main() -> None:
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    print("[START] topic2.py running")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
