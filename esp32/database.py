import os
import threading
import importlib
from typing import Any

class DBService:
	def __init__(self) -> None:
		self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
		self.port = int(os.getenv("MYSQL_PORT", "3306"))
		self.user = os.getenv("MYSQL_USER", "root")
		self.password = os.getenv("MYSQL_PASSWORD", "")
		self.database = os.getenv("MYSQL_DATABASE", "appdb")
		self.charset = "utf8mb4"
		self._lock = threading.Lock()

	def _connect(self):
		pymysql = importlib.import_module("pymysql")
		dict_cursor = importlib.import_module("pymysql.cursors").DictCursor
		return pymysql.connect(
			host=self.host,
			port=self.port,
			user=self.user,
			password=self.password,
			database=self.database,
			charset=self.charset,
			autocommit=True,
			cursorclass=dict_cursor,
		)

	def insert_play_request(self, rand_num: str, member_name: str, member_no: str, topic_name: str) -> None:
		with self._lock:
			conn = self._connect()
			try:
				with conn.cursor() as cur:
					cur.execute(
						"""
						INSERT INTO play_request_table(rand_num, member_name, member_no, topic_name)
						VALUES(%s, %s, %s, %s)
						""",
						(rand_num, member_name, member_no, topic_name),
					)
			finally:
				conn.close()

	def insert_play_result(self, rand_num: str, result_value: int) -> None:
		with self._lock:
			conn = self._connect()
			try:
				with conn.cursor() as cur:
					cur.execute(
						"""
						INSERT INTO play_result_table(rand_num, result_value)
						VALUES(%s, %s)
						ON DUPLICATE KEY UPDATE result_value=VALUES(result_value)
						""",
						(rand_num, int(result_value)),
					)
			finally:
				conn.close()

	def get_play_relation(self, rand_num: str) -> dict[str, Any] | None:
		conn = self._connect()
		try:
			with conn.cursor() as cur:
				cur.execute(
					"""
					SELECT
						p.rand_num,
						p.member_name,
						p.member_no,
						p.topic_name,
						r.result_value
					FROM play_request_table p
					LEFT JOIN play_result_table r ON r.rand_num = p.rand_num
					WHERE p.rand_num = %s
					""",
					(rand_num,),
				)
				row = cur.fetchone()
				return row
		finally:
			conn.close()


db = DBService()

__all__ = ["db", "DBService"]
