import json
import os
import time

import paho.mqtt.client as mqtt

# Broker settings (change via environment variables if needed)
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "qwer1234")

# Four main topics in the requested flow
TOPIC1_SENSOR = os.getenv("TOPIC1_SENSOR", "topic1")
TOPIC2_CAPTURE = os.getenv("TOPIC2_CAPTURE", "topic2")
TOPIC4_ACTUATOR = os.getenv("TOPIC4_ACTUATOR", "topic4")


def _publish_capture_command(client: mqtt.Client) -> None:
    payload = {
        "cmd": "capture",
        "ts": int(time.time()),
        "source": "topic1.py",
    }
    client.publish(TOPIC2_CAPTURE, json.dumps(payload), qos=1)
    print(f"[PUB] {TOPIC2_CAPTURE} <- {payload}")


def _publish_actuator_command(client: mqtt.Client, label: int) -> None:
    action = "OFF"
    if label in (0, 1):
        action = "ON"

    payload = {
        "label": label,
        "action": action,
        "ts": int(time.time()),
    }
    client.publish(TOPIC4_ACTUATOR, json.dumps(payload), qos=1)
    print(f"[PUB] {TOPIC4_ACTUATOR} <- {payload}")


def on_connect(client: mqtt.Client, userdata, flags, rc):
    if rc == 0:
        print("[OK] MQTT broker connected")
        client.subscribe(TOPIC1_SENSOR, qos=1)
        print(f"[SUB] {TOPIC1_SENSOR}")
    else:
        print(f"[ERROR] MQTT connect failed rc={rc}")


def on_message(client: mqtt.Client, userdata, msg):
    topic = msg.topic
    raw = msg.payload
    payload_text = raw.decode("utf-8", errors="ignore").strip()

    if topic == TOPIC1_SENSOR:
        print(f"[RECV] {TOPIC1_SENSOR} -> {payload_text}")
        if payload_text.upper() == "ON":
            _publish_capture_command(client)
            return

        label = None
        try:
            data = json.loads(payload_text)
            if isinstance(data, dict) and "label" in data:
                label = int(data["label"])
        except Exception:
            if payload_text.isdigit():
                label = int(payload_text)

        if label is not None:
            _publish_actuator_command(client, label)


def main() -> None:
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    print("[START] topic1.py running")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
