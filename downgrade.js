const sqlite3 = require('sqlite3');
const db = new sqlite3.Database('backend/youtube_ab_test.db');
db.run("UPDATE users SET plan = 'BASIC' WHERE email = 'godlove3854@gmail.com'", function(err) {
    if (err) console.error(err);
    else console.log('Downgraded user to BASIC. Rows affected:', this.changes);
});
