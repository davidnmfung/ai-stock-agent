'use client';

import { useEffect, useState } from 'react';

interface Signal {
  Ticker: string;
  Date: string;
  Price: number;
  Score: number;
  Summary?: string;
}

interface DashboardData {
  last_updated: string;
  total_signals: number;
  win_rate_t1: number;
  signals: Signal[];
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    fetch('/data/dashboard_data.json')
      .then((res) => res.json())
      .then((data) => setData(data))
      .catch((err) => console.error('Failed to load dashboard data:', err));
  }, []);

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center font-mono">
        <p className="text-xl animate-pulse text-blue-400">Loading AlphaPulse AI Terminal...</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8 font-sans selection:bg-blue-500 selection:text-white">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-800 pb-6 gap-4">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">
              AlphaPulse AI Terminal
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Institutional-Grade Quantitative Momentum & Event Catalyst Scanner
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 mr-2 animate-ping" />
              Live Feed Active
            </span>
            <span className="text-xs text-slate-500 font-mono">Sync: {data.last_updated}</span>
          </div>
        </div>

        {/* KPI Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Logged Signals</p>
            <p className="text-4xl font-extrabold text-white mt-2">{data.total_signals}</p>
            <p className="text-xs text-slate-500 mt-2">Historical breakout triggers stored</p>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Est. T+1 Win Rate</p>
            <p className="text-4xl font-extrabold text-emerald-400 mt-2">{data.win_rate_t1}%</p>
            <p className="text-xs text-slate-500 mt-2">Based on automated multi-day backtest</p>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Architecture Standard</p>
            <p className="text-lg font-bold text-indigo-400 mt-3">XERJ Corpus Hub Reference</p>
            <p className="text-xs text-slate-500 mt-1">Modular production design</p>
          </div>
        </div>

        {/* Signals Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/40">
            <h2 className="text-base font-semibold text-white">Live Breakout Signal History</h2>
            <span className="text-xs text-slate-400 font-mono">Source: data/signal_history.csv</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950/60 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800 font-mono">
                  <th className="px-6 py-3">Ticker</th>
                  <th className="px-6 py-3">Trigger Date</th>
                  <th className="px-6 py-3">Entry Price</th>
                  <th className="px-6 py-3">AI Score</th>
                  <th className="px-6 py-3">Catalyst & Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm">
                {data.signals.map((sig, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-6 py-4 font-bold font-mono text-blue-400">{sig.Ticker}</td>
                    <td className="px-6 py-4 text-slate-300 font-mono text-xs">{sig.Date}</td>
                    <td className="px-6 py-4 font-mono text-slate-200">
                      ${typeof sig.Price === 'number' ? sig.Price.toFixed(2) : sig.Price}
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 rounded font-mono font-semibold text-xs">
                        {sig.Score ?? 'N/A'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-xs">
                      {sig.Summary || 'Institutional volume surge & momentum breakout detected.'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </main>
  );
}