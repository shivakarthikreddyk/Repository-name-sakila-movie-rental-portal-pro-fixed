const express = require('express');
function createApp(query, logger = console) {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '16kb' }));

  function databaseError(res, error) {
    logger.error('Database request failed:', error.code || error.name);
    res.status(503).json({ error: 'Database is temporarily unavailable' });
  }

  app.use('/api', (req, res, next) => {
    for (const key of ['search', 'rating']) {
      if (req.query[key] !== undefined &&
          (typeof req.query[key] !== 'string' || req.query[key].length > 100)) {
        return res.status(400).json({ error: `${key} must be a string of at most 100 characters` });
      }
    }
    if (req.query.rating && !['G', 'PG', 'PG-13', 'R', 'NC-17'].includes(req.query.rating)) {
      return res.status(400).json({ error: 'Invalid movie rating' });
    }
    next();
  });

  app.get('/api/live', (req, res) => res.json({ status: 'UP' }));

  app.get('/api/health', async (req, res) => {
    try {
      // Check the seeded schema, not only whether MySQL accepts connections.
      const [state] = await query('SELECT COUNT(*) total FROM film');
      if (!Number(state.total)) throw new Error('Database is not initialized');
      res.json({ status: 'UP', database: 'CONNECTED', service: 'sakila-backend' });
    } catch (error) {
      logger.error('Database readiness failed:', error.code || error.name);
      res.status(503).json({ status: 'DOWN', database: 'UNAVAILABLE', service: 'sakila-backend' });
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
      databaseError(res, error);
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
      databaseError(res, error);
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
      databaseError(res, error);
    }
  });

  app.get('/api/rentals', async (req, res) => {
    try {
      const search = `%${req.query.search || ''}%`;
      const rows = await query(`
        SELECT r.rental_id, r.rental_date, r.return_date, f.title,
               CONCAT(c.first_name, ' ', c.last_name) customer
        FROM rental r
        JOIN customer c ON r.customer_id = c.customer_id
        JOIN inventory i ON r.inventory_id = i.inventory_id
        JOIN film f ON i.film_id = f.film_id
        WHERE f.title LIKE ? OR CONCAT(c.first_name, ' ', c.last_name) LIKE ?
        ORDER BY r.rental_date DESC
        LIMIT 100
      `, [search, search]);
      res.json(rows);
    } catch (error) {
      databaseError(res, error);
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
      databaseError(res, error);
    }
  });

  app.get('/api/stores', async (req, res) => {
    try {
      const search = `%${req.query.search || ''}%`;
      const rows = await query(`
        SELECT s.store_id, CONCAT(st.first_name, ' ', st.last_name) manager,
               a.address, ci.city,
               (SELECT COUNT(*) FROM inventory i WHERE i.store_id = s.store_id) inventory_count
        FROM store s
        JOIN staff st ON s.manager_staff_id = st.staff_id
        JOIN address a ON s.address_id = a.address_id
        JOIN city ci ON a.city_id = ci.city_id
        WHERE CONCAT(st.first_name, ' ', st.last_name) LIKE ? OR a.address LIKE ? OR ci.city LIKE ?
        ORDER BY s.store_id
      `, [search, search, search]);
      res.json(rows);
    } catch (error) {
      databaseError(res, error);
    }
  });

  app.use('/api', (req, res) => res.status(404).json({ error: 'API endpoint not found' }));
  app.use((error, req, res, next) => {
    res.status(400).json({ error: 'Invalid request' });
  });
  return app;
}

module.exports = { createApp };
