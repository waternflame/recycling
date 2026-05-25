import time
import paho.mqtt.client as mqtt

MQTT_HOST = "127.0.0.1"  
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/led"  

def on_connect(client, userdata, flags, rc):
    # rc가 0이어야 진짜로 서버 대문을 통과한 것입니다.
    if rc == 0:
        print("[OK] MQTT 브로커에 '비밀번호 인증'으로 성공적으로 연결되었습니다!")
        client.subscribe(MQTT_TOPIC)
    else:
        # 📍 false인데 비번이 틀리면 rc == 5 (인증 오류)가 뜹니다.
        print(f"[ERROR] 연결 거부되었습니다. 에러 코드(rc): {rc}")
        if rc == 5:
            print("[힌트] 아이디 또는 비밀번호가 서버 설정과 일치하지 않습니다.")

def on_message(client, userdata, msg):
    payload_str = msg.payload.decode("utf-8")
    print(f"[{msg.topic}] 수신된 데이터: {payload_str}")

# 4. MQTT 클라이언트 초기화 및 설정
client = mqtt.Client()

# 📍 [여기 필수 수정!] 아까 CMD로 만드신 ID와 비밀번호를 괄호 안에 적어줍니다.
client.username_pw_set("admin", "qwer1234")

client.on_connect = on_connect
client.on_message = on_message

print("[START] MQTT 엔드포인트 서버를 시작합니다.")
client.connect(MQTT_HOST, MQTT_PORT, 60)

client.loop_forever()
