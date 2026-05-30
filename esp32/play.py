import json
import secrets
from datetime import datetime
from typing import Any

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from esp32.database import db

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USERNAME = "admin"
MQTT_PASSWORD = "qwer1234"

MQTT_RANDOM_TOPIC = "esp32/random"


class ExecuteRequest(BaseModel):
	logged_in: bool = Field(..., description="로그인 상태")
	qr_device_id: str = Field(..., description="QR로 읽은 기기 ID")
	member_id: str = Field(..., description="회원 ID")
	member_info: dict[str, Any] = Field(default_factory=dict)
	device_info: dict[str, Any] = Field(default_factory=dict)

# MQTT 구독/발행과 DB 저장을 담당하는 서비스 클래스
class PlayService:
	# MQTT 클라이언트를 생성하고 인증 정보를 설정한다.
	def __init__(self) -> None:
		self.client = mqtt.Client()
		self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
		self.client.on_connect = self._on_connect
		self.connected = False

	# 브로커에 연결하고 MQTT 네트워크 루프를 시작한다.
	def start(self) -> None:
		if self.connected:
			return
		self.client.connect(MQTT_HOST, MQTT_PORT, 60)
		self.client.loop_start()
		self.connected = True

	# MQTT 네트워크 루프를 중지하고 연결을 종료한다.
	def stop(self) -> None:
		if not self.connected:
			return
		self.client.loop_stop()
		self.client.disconnect()
		self.connected = False

	# MQTT 연결 결과를 로그로 남긴다.
	def _on_connect(self, client, userdata, flags, rc):
		if rc == 0:
			print("[PLAY] MQTT 연결 성공")
		else:
			print(f"[PLAY] MQTT 연결 실패 rc={rc}")

	# 실행 요청 식별용 6자리 난수 키를 생성한다.
	def _new_random_key(self) -> str:
		return str(secrets.randbelow(900000) + 100000)

	# 실행 버튼 요청을 검증하고 DB 저장 후 random 토픽으로 발행한다.
	def handle_execute_button(self, req: ExecuteRequest) -> dict[str, Any]:
		if not req.logged_in:
			raise ValueError("로그인 상태가 아닙니다.")

		random_key = self._new_random_key()
		member_payload = {
			"member_id": req.member_id,
			**req.member_info,
		}
		device_payload = {
			"device_id": req.qr_device_id,
			**req.device_info,
		}

		execute_payload = {
			"random_key": random_key,
			"device": device_payload,
			"member": member_payload,
			"requested_at": datetime.utcnow().isoformat(timespec="seconds"),
		}

		db.upsert_member(req.member_id, member_payload)
		db.upsert_device(req.qr_device_id, MQTT_RANDOM_TOPIC, device_payload)
		db.create_execution(
			random_key=random_key,
			device_id=req.qr_device_id,
			member_id=req.member_id,
			execute_payload=execute_payload,
		)

		self.client.publish(
			MQTT_RANDOM_TOPIC,
			json.dumps(execute_payload, ensure_ascii=False),
			qos=1,
		)
        
		print(
			f"[PLAY] execute -> topic={MQTT_RANDOM_TOPIC}, random_key={random_key}, "
			f"device={req.qr_device_id}, member={req.member_id}"
		)
		return execute_payload

# FastAPI 앱과 서비스 인스턴스를 생성한다.
app = FastAPI(title="ESP32 Play Server")
service = PlayService()

# 서버 시작 시 MQTT 연결을 시작한다.
@app.on_event("startup")
def on_startup() -> None:
	service.start()

# 서버 종료 시 MQTT 연결을 정리한다.
@app.on_event("shutdown")
def on_shutdown() -> None:
	service.stop()

# 실행 버튼 요청을 처리한다.
@app.post("/execute")
def execute(req: ExecuteRequest) -> dict[str, Any]:
	try:
		payload = service.handle_execute_button(req)
		return {"ok": True, "payload": payload}
	except ValueError as exc:
		raise HTTPException(status_code=400, detail=str(exc)) from exc
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"execute failed: {exc}") from exc

# 난수 키 기준 실행/결과 조인 데이터를 조회한다.
@app.get("/executions/{random_key}")
def get_execution(random_key: str) -> dict[str, Any]:
	relation = db.get_execution_relation(random_key)
	if relation is None:
		raise HTTPException(status_code=404, detail="not found")
	return {"ok": True, "relation": relation}

