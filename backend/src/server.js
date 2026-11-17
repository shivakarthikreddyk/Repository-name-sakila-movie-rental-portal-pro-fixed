const mysql = require('mysql2/promise');
const { createApp } = require('./app');

if (!process.env.DB_PASSWORD) throw new Error('DB_PASSWORD is required');

const pool = mysql.createPool({
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT || 3306),
  user: process.env.DB_USER || 'sakila',
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME || 'sakila',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 100,
  connectTimeout: 5000,
  timezone: 'Z',
  dateStrings: true,
});

const app = createApp(async (sql, params = []) => {
  const [rows] = await pool.execute(sql, params);
  return rows;
});
const port = Number(process.env.PORT || 5000);
const server = app.listen(port, '0.0.0.0', () => console.log(`Sakila backend listening on ${port}`));

function shutdown() {
  const timeout = setTimeout(() => process.exit(1), 10000);
  timeout.unref();
  server.close(async () => {
    await pool.end();
    clearTimeout(timeout);
    process.exit(0);
  });
}
process.once('SIGTERM', shutdown);
process.once('SIGINT', shutdown);
