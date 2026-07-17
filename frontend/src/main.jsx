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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function loadDashboard() {
    setLoading(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/dashboard`);
      if (!res.ok) throw new Error('Dashboard API failed');
      setDashboard(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function loadList(selectedTab = tab) {
    setLoading(true); setError('');
    try {
      const query = search ? `?search=${encodeURIComponent(search)}` : '';
      const res = await fetch(`${API_BASE}/${selectedTab}${query}`);
      if (!res.ok) throw new Error(`${selectedTab} API failed`);
      setRows(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    if (tab === 'dashboard') loadDashboard();
    else loadList(tab);
  }, [tab]);

  function renderRows() {
    if (!rows.length) return <p className="empty">No records found.</p>;
    const cols = Object.keys(rows[0]);
    return <div className="tableWrap"><table><thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i}>{cols.map(c => <td key={c}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody></table></div>;
  }

  return <div className="app">
    <aside>
      <h1>Sakila Pro</h1>
      <p>Movie Rental Portal</p>
      {['dashboard','movies','customers','rentals','actors','stores'].map(t => <button key={t} onClick={() => setTab(t)} className={tab===t?'active':''}>{t}</button>)}
    </aside>
    <main>
      <header>
        <div><h2>{tab.toUpperCase()}</h2><p>Docker + Kubernetes learning project</p></div>
        {tab !== 'dashboard' && <div className="search"><input placeholder="Search..." value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==='Enter') loadList();}}/><button onClick={()=>loadList()}>Search</button></div>}
      </header>
      {loading && <div className="info">Loading...</div>}
      {error && <div className="error">{error}</div>}
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
      {tab !== 'dashboard' && renderRows()}
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
