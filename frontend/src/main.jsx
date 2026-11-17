import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const API_BASE = '/api';

function Card({ title, value }) {
  return <div className="card"><p>{title}</p><h2>{value}</h2></div>;
}

function App() {
  const [tab, setTab] = useState('dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setRows([]); setDashboard(null);
    async function load() {
      try {
        const query = tab !== 'dashboard' && submittedSearch
          ? `?search=${encodeURIComponent(submittedSearch)}` : '';
        const res = await fetch(`${API_BASE}/${tab}${query}`, { signal: controller.signal });
        if (!res.ok) throw new Error(`Unable to load ${tab}. Please try again.`);
        const data = await res.json();
        if (!controller.signal.aborted) {
          if (tab === 'dashboard') setDashboard(data);
          else setRows(data);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(e.message);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [tab, submittedSearch]);

  function selectTab(nextTab) {
    if (nextTab === tab) return;
    setTab(nextTab); setSearch(''); setSubmittedSearch('');
    setRows([]); setDashboard(null); setError(''); setLoading(true);
  }

  function renderRows() {
    if (!rows.length) return <p className="empty">No records found.</p>;
    const cols = Object.keys(rows[0]);
    return <div className="tableWrap"><table><thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{cols.map(c => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody></table></div>;
  }

  return <div className="app">
    <aside>
      <h1>Sakila Pro</h1>
      <p>Movie Rental Portal</p>
      {['dashboard','movies','customers','rentals','actors','stores'].map(t => <button key={t} onClick={() => selectTab(t)} aria-current={tab===t?'page':undefined} className={tab===t?'active':''}>{t}</button>)}
    </aside>
    <main>
      <header>
        <div><h2>{tab.toUpperCase()}</h2><p>Explore movies, customers, and rental activity</p></div>
        {tab !== 'dashboard' && <form className="search" onSubmit={e=>{e.preventDefault();setSubmittedSearch(search.trim());}}><input aria-label={`Search ${tab}`} placeholder="Search..." maxLength={100} value={search} onChange={e=>setSearch(e.target.value)}/><button type="submit">Search</button></form>}
      </header>
      {loading && <div className="info" role="status">Loading...</div>}
      {error && <div className="error" role="alert">{error}</div>}
      {tab === 'dashboard' && dashboard && <>
        <section className="cards">
          <Card title="Total Movies" value={dashboard.totalMovies} />
          <Card title="Customers" value={dashboard.totalCustomers} />
          <Card title="Rentals" value={dashboard.totalRentals} />
          <Card title="Revenue" value={`$${Number(dashboard.totalRevenue).toFixed(2)}`} />
        </section>
        <section className="panel"><h3>Top Rented Movies</h3>{dashboard.topMovies?.map(m => <div className="bar" key={m.title}><span>{m.title}</span><strong>{m.rentals}</strong></div>)}</section>
        <section className="panel"><h3>Monthly Revenue</h3>{dashboard.monthlyRevenue?.map(m => <div className="bar" key={m.month}><span>{m.month}</span><strong>${Number(m.revenue).toFixed(2)}</strong></div>)}</section>
      </>}
      {tab !== 'dashboard' && !loading && !error && renderRows()}
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
