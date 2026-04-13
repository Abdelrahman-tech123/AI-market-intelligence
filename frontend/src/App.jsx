import React, { useState } from 'react';
import axios from 'axios';
import {
  Search, Loader2, ShoppingCart, TrendingUp, AlertTriangle,
  CheckCircle, Zap, Info, ExternalLink, BarChart3
} from 'lucide-react';

// frontend : npm run dev
// backend : watchfiles "uvicorn main:app"

function App() {
  const [keyword, setKeyword] = useState('');
  const [data, setData] = useState({ results: [], market_average: 0 });
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!keyword) return;
    setLoading(true);
    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/search?keyword=${keyword}`);
      setData(response.data);
      setActiveTab('all');
    } catch (error) {
      console.error("Error:", error);
      alert("System Offline");
    }
    setLoading(false);
  };

  const filteredResults = activeTab === 'all'
    ? data.results
    : data.results.filter(item => item.source === activeTab);

  const availableSources = ['all', ...new Set(data.results.map(item => item.source))];

  return (
    <div className="min-h-screen bg-[#020617] text-slate-100 font-sans selection:bg-blue-500/30">
      {/* Navigation */}
      <nav className="border-b border-slate-800 bg-[#020617]/80 backdrop-blur-xl sticky top-0 z-50 p-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2 font-black text-2xl tracking-tighter text-white">
            <div className="bg-blue-600 p-1.5 rounded-lg">
              <Zap size={24} fill="white" />
            </div>
            <span>CORE<span className="text-blue-700 ">AI</span></span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-3 py-1 bg-slate-900 border border-slate-800 rounded-full text-[10px] font-bold text-slate-400 uppercase tracking-widest">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              BART-Large-MNLI Active
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 pt-12 pb-20">
        {/* Hero & Search */}
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-6xl font-black mb-4 tracking-tight">
            Market <span className="text-blue-500">Intelligence</span>
          </h1>
          <p className="text-slate-400 text-sm md:text-base max-w-xl mx-auto">
            Real-time cross-platform scraping with Zero-Shot AI for deal quality and scam detection.
          </p>

          <form onSubmit={handleSearch} className="mt-8 flex gap-2 justify-center max-w-2xl mx-auto relative">
            <input
              type="text"
              placeholder="Search products (e.g. RTX 4090, iPhone 15)..."
              className="w-full bg-slate-900/80 border border-slate-700 p-4 pl-6 rounded-2xl focus:ring-2 focus:ring-blue-500 outline-none transition-all placeholder:text-slate-600 shadow-2xl"
              onChange={(e) => setKeyword(e.target.value)}
            />
            <button
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 text-white px-6 rounded-2xl font-bold flex items-center gap-2 transition-all disabled:opacity-50"
            >
              {loading ? <Loader2 className="animate-spin" /> : <Search size={20} />}
              <span className="hidden md:inline">Analyze</span>
            </button>
          </form>
        </div>

        {/* Global Market Stats */}
        {data.results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
            <div className="bg-blue-600/10 border border-blue-500/20 p-4 rounded-2xl flex items-center gap-4">
              <div className="bg-blue-600/20 p-3 rounded-xl text-blue-400">
                <BarChart3 size={24} />
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-blue-400 tracking-wider">Market Average</p>
                <p className="text-2xl font-black text-white">{data.market_average}</p>
              </div>
            </div>
            {/* Add more stats cards here if needed */}
          </div>
        )}

        {/* Filters */}
        {data.results.length > 0 && (
          <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-2 no-scrollbar">
            {availableSources.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-2 rounded-xl text-xs font-bold capitalize transition-all whitespace-nowrap border ${activeTab === tab
                  ? 'bg-white text-black border-white'
                  : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-600'
                  }`}
              >
                {tab}
              </button>
            ))}
          </div>
        )}

        {/* Results Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredResults.map((product, index) => (
            <div
              key={index}
              className={`group relative bg-slate-900/50 border rounded-3xl overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-blue-500/5 ${product.ai_status === '🚩 Flagged' ? 'border-rose-500/30' : 'border-slate-800 hover:border-slate-600'
                }`}
            >
              {/* Image Section */}
              <div className="relative h-56 bg-white/5 p-6 flex items-center justify-center overflow-hidden border-b border-slate-800">
                <img
                  src={product.image || "https://via.placeholder.com/150"}
                  className="h-full object-contain group-hover:scale-105 transition-transform duration-500"
                  alt={product.title}
                />

                {/* Source Badge */}
                <div className="absolute top-4 left-4 bg-black/80 backdrop-blur-md text-[9px] font-black px-2.5 py-1 rounded-lg border border-white/10 text-white uppercase tracking-tighter">
                  {product.source}
                </div>

                {/* AI Deal Badge */}
                <div className={`absolute top-4 right-4 text-[10px] font-bold px-3 py-1 rounded-lg shadow-2xl backdrop-blur-md border ${product.ai_deal.includes('Steal') ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                  product.ai_deal.includes('Suspicious') ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' :
                    product.ai_deal.includes('Premium') ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                      'bg-blue-500/20 text-blue-400 border-blue-500/30'
                  }`}>
                  {product.ai_deal}
                </div>
              </div>

              {/* Info Section */}
              <div className="p-6">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h3 className="font-bold text-slate-100 text-sm line-clamp-2 leading-relaxed h-10">
                    {product.title}
                  </h3>
                </div>

                <div className="flex items-baseline gap-2 mt-4">
                  <span className="text-2xl font-black text-white">{product.price}</span>
                </div>

                <div className="mt-6 flex items-center justify-between">
                  {/* Status Indicator */}
                  <div className={`flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-md ${product.ai_status === 'Legit' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'
                    }`}>
                    {product.ai_status === 'Legit' ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                    {product.ai_status}
                  </div>

                  <a
                    href={product.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[10px] font-bold text-blue-400 hover:text-blue-300 transition-colors uppercase tracking-widest"
                  >
                    Details <ExternalLink size={12} />
                  </a>
                </div>
              </div>

              {/* Warning Overlay for Flagged items */}
              {product.ai_status === '🚩 Flagged' && (
                <div className="absolute inset-0 bg-rose-950/10 pointer-events-none" />
              )}
            </div>
          ))}
        </div>

        {/* Empty State */}
        {data.results.length === 0 && !loading && (
          <div className="text-center py-24 border-2 border-dashed border-slate-800 rounded-[3rem] bg-slate-900/20">
            <div className="bg-slate-800 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6">
              <ShoppingCart className="text-slate-500" size={32} />
            </div>
            <h3 className="text-xl font-bold text-white mb-2">No Market Data Yet</h3>
            <p className="text-slate-500 text-sm max-w-xs mx-auto">
              Enter a product keyword above to start the AI scraping process.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;