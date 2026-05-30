import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"


# UTC 현재 시각을 ISO 문자열로 반환한다.
def _utc_now() -> str:
	return datetime.utcnow().isoformat(timespec="seconds")


class DBService:
	# DB 경로와 락을 준비하고 테이블을 초기화한다.
	def __init__(self, db_path: Path) -> None:
		self.db_path = db_path
		self._lock = threading.Lock()
		self._init_db()

	# 외래키가 활성화된 SQLite 연결을 생성한다.
	def _connect(self) -> sqlite3.Connection:
		conn = sqlite3.connect(self.db_path)
		conn.row_factory = sqlite3.Row
		conn.execute("PRAGMA foreign_keys = ON")
		return conn

	# 회원/기기/실행/결과 테이블을 생성한다.
	def _init_db(self) -> None:
		with self._connect() as conn:
			conn.executescript(
				"""
				CREATE TABLE IF NOT EXISTS members (
					member_id TEXT PRIMARY KEY,
					metadata_json TEXT NOT NULL,
					created_at TEXT NOT NULL
				);

				CREATE TABLE IF NOT EXISTS devices (
					device_id TEXT PRIMARY KEY,
					topic TEXT NOT NULL,
					metadata_json TEXT NOT NULL,
					created_at TEXT NOT NULL
				);

				CREATE TABLE IF NOT EXISTS executions (
					random_key TEXT PRIMARY KEY,
					device_id TEXT NOT NULL,
					member_id TEXT NOT NULL,
					execute_payload_json TEXT NOT NULL,
					execute_pressed_at TEXT NOT NULL,
					status TEXT NOT NULL,
					FOREIGN KEY(device_id) REFERENCES devices(device_id),
					FOREIGN KEY(member_id) REFERENCES members(member_id)
				);

				CREATE TABLE IF NOT EXISTS execution_results (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					random_key TEXT NOT NULL UNIQUE,
					result_value INTEGER NOT NULL,
					sensor_payload_json TEXT NOT NULL,
					image_path TEXT,
					completed_at TEXT NOT NULL,
					FOREIGN KEY(random_key) REFERENCES executions(random_key)
				);
				"""
			)

	# 회원 정보를 삽입하거나 최신 데이터로 갱신한다.
	def upsert_member(self, member_id: str, metadata: dict[str, Any]) -> None:
		with self._lock, self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO members(member_id, metadata_json, created_at)
				VALUES(?, ?, ?)
				ON CONFLICT(member_id)
				DO UPDATE SET metadata_json=excluded.metadata_json
				""",
				(member_id, json.dumps(metadata, ensure_ascii=False), _utc_now()),
			)

	# 기기 정보를 삽입하거나 토픽/메타데이터를 갱신한다.
	def upsert_device(self, device_id: str, topic: str, metadata: dict[str, Any]) -> None:
		with self._lock, self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO devices(device_id, topic, metadata_json, created_at)
				VALUES(?, ?, ?, ?)
				ON CONFLICT(device_id)
				DO UPDATE SET topic=excluded.topic, metadata_json=excluded.metadata_json
				""",
				(device_id, topic, json.dumps(metadata, ensure_ascii=False), _utc_now()),
			)

	# 실행 버튼 요청을 난수 키 기준으로 저장한다.
	def create_execution(
		self,
		random_key: str,
		device_id: str,
		member_id: str,
		execute_payload: dict[str, Any],
	) -> None:
		with self._lock, self._connect() as conn:
			conn.execute(
				"""
				INSERT INTO executions(
					random_key,
					device_id,
					member_id,
					execute_payload_json,
					execute_pressed_at,
					status
				)
				VALUES(?, ?, ?, ?, ?, ?)
				""",
				(
					random_key,
					device_id,
					member_id,
					json.dumps(execute_payload, ensure_ascii=False),
					_utc_now(),
					"requested",
				),
			)

	# 센서 처리 결과를 동기 저장하고 실행 상태를 완료로 바꾼다.
	def save_result_sync(
		self,
		random_key: str,
		result_value: int,
		sensor_payload: dict[str, Any],
		image_path: str | None = None,
	) -> None:
		with self._lock, self._connect() as conn:
			row = conn.execute(
				"SELECT random_key FROM executions WHERE random_key = ?",
				(random_key,),
			).fetchone()
			if row is None:
				raise ValueError(f"unknown random_key: {random_key}")

			conn.execute(
				"""
				INSERT INTO execution_results(
					random_key,
					result_value,
					sensor_payload_json,
					image_path,
					completed_at
				)
				VALUES(?, ?, ?, ?, ?)
				ON CONFLICT(random_key)
				DO UPDATE SET
					result_value=excluded.result_value,
					sensor_payload_json=excluded.sensor_payload_json,
					image_path=excluded.image_path,
					completed_at=excluded.completed_at
				""",
				(
					random_key,
					int(result_value),
					json.dumps(sensor_payload, ensure_ascii=False),
					image_path,
					_utc_now(),
				),
			)

			conn.execute(
				"UPDATE executions SET status = ? WHERE random_key = ?",
				("completed", random_key),
			)

	# 난수 키 기준으로 실행 요청과 결과를 조인해 반환한다.
	def get_execution_relation(self, random_key: str) -> dict[str, Any] | None:
		with self._connect() as conn:
			row = conn.execute(
				"""
				SELECT
					e.random_key,
					e.device_id,
					e.member_id,
					e.execute_payload_json,
					e.execute_pressed_at,
					e.status,
					r.result_value,
					r.sensor_payload_json,
					r.image_path,
					r.completed_at
				FROM executions e
				LEFT JOIN execution_results r ON r.random_key = e.random_key
				WHERE e.random_key = ?
				""",
				(random_key,),
			).fetchone()

			if row is None:
				return None

			return {
				"random_key": row["random_key"],
				"device_id": row["device_id"],
				"member_id": row["member_id"],
				"execute_payload": json.loads(row["execute_payload_json"]),
				"execute_pressed_at": row["execute_pressed_at"],
				"status": row["status"],
				"result_value": row["result_value"],
				"sensor_payload": (
					json.loads(row["sensor_payload_json"])
					if row["sensor_payload_json"]
					else None
				),
				"image_path": row["image_path"],
				"completed_at": row["completed_at"],
			}


db = DBService(DB_PATH)

