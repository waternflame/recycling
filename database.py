import sqlite3

DB_PATH = "classification.db"

# DB 초기화
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY,
            file_path TEXT,
            label INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# 저장
def save_results(results):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for result in results:
        cursor.execute('INSERT INTO results (file_path, label) VALUES (?, ?)',
                      (result['file_path'], result['label']))
    conn.commit()
    conn.close()
    print(f"✅ {len(results)}개 저장됨")

def save_result(file_path, label):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO results (file_path, label) VALUES (?, ?)',
        (file_path, label)
    )
    conn.commit()
    conn.close()
    print(f"saved 1 result: {file_path} -> {label}")

if __name__ == "__main__":
    init_db()
    print("✅ DB 초기화 완료")
