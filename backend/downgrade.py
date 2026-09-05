import sqlite3
conn = sqlite3.connect('youtube_ab_test.db')
conn.execute("UPDATE users SET plan = 'BASIC' WHERE id = 1")
conn.commit()
print('Downgraded')
