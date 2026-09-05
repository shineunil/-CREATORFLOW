import sqlite3
conn = sqlite3.connect('youtube_ab_test.db')
cursor = conn.cursor()

cursor.execute('DELETE FROM metrics_logs;')
cursor.execute('DELETE FROM variations;')
cursor.execute('DELETE FROM ab_tests;')
cursor.execute('DELETE FROM videos;')
cursor.execute("DELETE FROM channels WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test_e2e_%');")
cursor.execute("DELETE FROM users WHERE email LIKE 'test_e2e_%';")

conn.commit()
conn.close()
print("Data fully cleared.")
