import sqlite3


def setup_database(database_path):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            title TEXT,
            karma INTEGER,
            created_utc INTEGER,
            closing_at INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS karma_changes (
            id TEXT,
            timestamp INTEGER,
            karma INTEGER,
            FOREIGN KEY(id) REFERENCES posts(id)
        )
    ''')
    conn.commit()
    conn.close()

def get_karma_changes(post_id, database_path):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, karma FROM karma_changes WHERE id = ?", (post_id,))
    data = cursor.fetchall()
    conn.close()
    return data


