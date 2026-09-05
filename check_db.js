const sqlite3 = require('sqlite3');
const db = new sqlite3.Database('backend/youtube_ab_test.db');
db.all("SELECT email, plan FROM users", (err, rows) => {
    if (err) console.error(err);
    console.log(rows);
});
