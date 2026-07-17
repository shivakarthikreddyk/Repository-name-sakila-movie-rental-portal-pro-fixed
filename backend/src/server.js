require('dd-trace').init({
  service: 'sakila-backend',
  env: 'local',
  version: '1.0.0',
  logInjection: true
});
const express = require('express');
const cors = require('cors');
const mysql = require('mysql2/promise');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 5000;

const pool = mysql.createPool({
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 3306,
  user: process.env.DB_USER || 'sakila',
  password: process.env.DB_PASSWORD || 'p_ssW0rd',
  database: process.env.DB_NAME || 'sakila',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

async function query(sql, params = []) {
  const [rows] = await pool.execute(sql, params);
  return rows;
}

app.get('/api/health', async (req, res) => {
  try {
    await query('SELECT 1');
    res.json({ status: 'UP', database: 'CONNECTED', service: 'sakila-backend' });
  } catch (error) {
    res.status(500).json({ status: 'DOWN', error: error.message });
  }
});

app.get('/api/dashboard', async (req, res) => {
  try {
    const [movies] = await query('SELECT COUNT(*) total FROM film');
    const [customers] = await query('SELECT COUNT(*) total FROM customer');
    const [rentals] = await query('SELECT COUNT(*) total FROM rental');
    const [revenue] = await query('SELECT IFNULL(SUM(amount),0) total FROM payment');
    const topMovies = await query(`
      SELECT f.title, COUNT(r.rental_id) rentals
      FROM rental r
      JOIN inventory i ON r.inventory_id = i.inventory_id
      JOIN film f ON i.film_id = f.film_id
      GROUP BY f.title
      ORDER BY rentals DESC
      LIMIT 8
    `);
    const monthlyRevenue = await query(`
      SELECT DATE_FORMAT(payment_date, '%Y-%m') month, ROUND(SUM(amount),2) revenue
      FROM payment
      GROUP BY DATE_FORMAT(payment_date, '%Y-%m')
      ORDER BY month
      LIMIT 12
    `);
    res.json({
      totalMovies: movies.total,
      totalCustomers: customers.total,
      totalRentals: rentals.total,
      totalRevenue: Number(revenue.total),
      topMovies,
      monthlyRevenue
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/movies', async (req, res) => {
  try {
    const search = `%${req.query.search || ''}%`;
    const rating = req.query.rating || '';
    const rows = await query(`
      SELECT f.film_id, f.title, f.release_year, f.rating, f.length, c.name category
      FROM film f
      LEFT JOIN film_category fc ON f.film_id = fc.film_id
      LEFT JOIN category c ON fc.category_id = c.category_id
      WHERE f.title LIKE ? AND (? = '' OR f.rating = ?)
      ORDER BY f.title
      LIMIT 100
    `, [search, rating, rating]);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/customers', async (req, res) => {
  try {
    const search = `%${req.query.search || ''}%`;
    const rows = await query(`
      SELECT c.customer_id, c.first_name, c.last_name, c.email, c.active,
             a.address, ci.city
      FROM customer c
      JOIN address a ON c.address_id = a.address_id
      JOIN city ci ON a.city_id = ci.city_id
      WHERE c.first_name LIKE ? OR c.last_name LIKE ? OR c.email LIKE ?
      ORDER BY c.customer_id
      LIMIT 100
    `, [search, search, search]);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/rentals', async (req, res) => {
  try {
    const rows = await query(`
      SELECT r.rental_id, r.rental_date, r.return_date, f.title,
             CONCAT(c.first_name, ' ', c.last_name) customer
      FROM rental r
      JOIN customer c ON r.customer_id = c.customer_id
      JOIN inventory i ON r.inventory_id = i.inventory_id
      JOIN film f ON i.film_id = f.film_id
      ORDER BY r.rental_date DESC
      LIMIT 100
    `);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/actors', async (req, res) => {
  try {
    const search = `%${req.query.search || ''}%`;
    const rows = await query(`
      SELECT a.actor_id, a.first_name, a.last_name, COUNT(fa.film_id) film_count
      FROM actor a
      LEFT JOIN film_actor fa ON a.actor_id = fa.actor_id
      WHERE a.first_name LIKE ? OR a.last_name LIKE ?
      GROUP BY a.actor_id, a.first_name, a.last_name
      ORDER BY film_count DESC
      LIMIT 100
    `, [search, search]);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/stores', async (req, res) => {
  try {
    const rows = await query(`
      SELECT s.store_id, CONCAT(st.first_name, ' ', st.last_name) manager,
             a.address, ci.city,
             (SELECT COUNT(*) FROM inventory i WHERE i.store_id = s.store_id) inventory_count
      FROM store s
      JOIN staff st ON s.manager_staff_id = st.staff_id
      JOIN address a ON s.address_id = a.address_id
      JOIN city ci ON a.city_id = ci.city_id
      ORDER BY s.store_id
    `);
    res.json(rows);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(PORT, () => console.log(`Sakila backend running on port ${PORT}`));
