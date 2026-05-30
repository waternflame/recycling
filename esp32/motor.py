import paho.mqtt.client as mqtt

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_RESULT_TOPIC = "esp32/motor"

# 분류 결과(0/1/2)를 모터 제어 토픽으로 발행한다.
def handle_classification_result(result: int) -> int:
	result = int(result)
	publisher = mqtt.Client()
	publisher.username_pw_set("admin", "qwer1234")
	publisher.connect(MQTT_HOST, MQTT_PORT, 60)
	publisher.publish(MQTT_RESULT_TOPIC, str(result), qos=1)
	publisher.disconnect()
	return result
