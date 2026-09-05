import sqlite3
conn = sqlite3.connect("backend/youtube_ab_tester.db")
c = conn.cursor()
c.execute("SELECT email, plan FROM users")
print(c.fetchall())
conn.close()
