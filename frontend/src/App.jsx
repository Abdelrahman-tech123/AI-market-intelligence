import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Search, Loader2, ShoppingCart, AlertTriangle, CheckCircle,
  Zap, ExternalLink, BarChart3, Layers, Info, ShieldCheck, Sun, Moon
} from 'lucide-react';

function App() {
  const [keyword, setKeyword] = useState('');
  const [data, setData] = useState({ results: [], market_average: "$0.00", total_found: 0, legit_count: 0 });
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [statusMessage, setStatusMessage] = useState('');

  // Theme & Currency States
  const [darkMode, setDarkMode] = useState(true);
  const [currency, setCurrency] = useState('USD');
  const [egpRate, setEgpRate] = useState(47.50);

  // Sync state changes explicitly with HTML root class list to prevent styling crashes
  useEffect(() => {
    const root = window.document.documentElement;
    if (darkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [darkMode]);

  // Fetch Live USD to EGP Exchange Rate Safely on Mount
  useEffect(() => {
    const fetchExchangeRate = async () => {
      try {
        const res = await axios.get('https://open.er-api.com/v6/latest/USD');
        if (res?.data?.rates?.EGP) {
          setEgpRate(Number(res.data.rates.EGP));
        }
      } catch (error) {
        console.error("Failed to fetch live currency rates, using fallback.", error);
      }
    };
    fetchExchangeRate();
  }, []);

  // Safe Currency Converter Utility
  const formatCurrency = (priceStr) => {
    if (!priceStr) return currency === 'USD' ? '$0.00' : '0.00 EGP';
    const targetStr = String(priceStr);
    const cleanedStr = targetStr.replace(/[^0-9.-]+/g, '');
    const numericValue = parseFloat(cleanedStr);

    if (isNaN(numericValue)) return targetStr;

    try {
      if (currency === 'EGP') {
        const converted = numericValue * egpRate;
        return `${converted.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} EGP`;
      }
      return `$${numericValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    } catch (err) {
      return currency === 'EGP' ? `${(numericValue * egpRate).toFixed(2)} EGP` : `$${numericValue.toFixed(2)}`;
    }
  };

  const filteredResults = activeTab === 'all'
    ? data?.results || []
    : (data?.results || []).filter(item => item?.source === activeTab);

  const availableSources = ['all', ...new Set((data?.results || []).map(item => item?.source).filter(Boolean))];

  const getValueScoreColor = (score) => {
    const numScore = Number(score) || 0;
    if (numScore >= 80) return 'text-emerald-500 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    if (numScore >= 50) return 'text-blue-500 dark:text-blue-400 bg-blue-500/10 border-blue-500/30';
    if (numScore >= 35) return 'text-amber-500 dark:text-amber-400 bg-amber-500/10 border-amber-500/30';
    return 'text-rose-500 dark:text-rose-400 bg-rose-500/10 border-rose-500/30';
  };

  const getValueBarColor = (score) => {
    const numScore = Number(score) || 0;
    if (numScore >= 80) return 'bg-emerald-500';
    if (numScore >= 50) return 'bg-blue-500';
    if (numScore >= 35) return 'bg-amber-500';
    return 'bg-rose-500';
  };

  return (
    <div className={`min-h-screen font-sans selection:bg-indigo-500/30 antialiased transition-colors duration-300 ${darkMode ? 'bg-[#030712] text-slate-100' : 'bg-slate-50 text-slate-800'
      }`}>

      {/* Navigation */}
      <nav className={`border-b sticky top-0 z-50 p-4 backdrop-blur-md transition-colors ${darkMode ? 'border-slate-900 bg-[#030712]/70 text-white' : 'border-slate-200 bg-white/70 text-slate-800'
        }`}>
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2.5 font-black text-2xl tracking-tighter">
            <div className="bg-gradient-to-tr from-amber-500 to-orange-600 p-2 rounded-xl shadow-lg shadow-orange-500/20">
              <Zap size={22} fill="white" className="text-white" />
            </div>
            <span>AMAI<span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-500">.ENG</span></span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setCurrency(prev => prev === 'USD' ? 'EGP' : 'USD')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${darkMode ? 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800' : 'bg-slate-100 border-slate-200 text-slate-700 hover:bg-slate-200'
                }`}
              title={`Current Rate: 1 USD = ${egpRate.toFixed(2)} EGP`}
            >
              Convert to {currency === 'USD' ? 'EGP' : 'USD'}
            </button>

            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`p-2 rounded-lg transition-all border ${darkMode ? 'bg-slate-900 border-slate-800 text-amber-400 hover:bg-slate-800' : 'bg-slate-100 border-slate-200 text-indigo-600 hover:bg-slate-200'
                }`}
            >
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
            </button>

            <div className={`hidden sm:flex items-center gap-2 px-3.5 py-1.5 border rounded-full text-[10px] font-bold uppercase tracking-widest ${darkMode ? 'bg-slate-900 border-slate-800 text-slate-400' : 'bg-slate-100 border-slate-200 text-slate-500'
              }`}>
              <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              BART Analysis Active
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 pt-16 pb-24">
        {/* Hero Banner Section */}
        <div className="text-center mb-16">
          <h1 className={`text-4xl sm:text-6xl font-black mb-4 tracking-tight ${darkMode ? 'text-white' : 'text-slate-900'}`}>
            AMAI <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 via-orange-500 to-yellow-400">Market Intelligence</span>
          </h1>
          <p className={`text-sm sm:text-base max-w-xl mx-auto font-medium ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>
            Cross-platform comparative analysis driven by semantic machine learning logic.
          </p>

          <form onSubmit={async (e) => {
            e.preventDefault();
            if (!keyword) return;

            setLoading(true);
            setStatusMessage('Searching marketplaces...');

            const statusTimer = setTimeout(() => {
              setStatusMessage('Analyzing with AI (BART Engine)...');
            }, 1200);

            try {
              const response = await axios.get(`http://127.0.0.1:8000/api/search?keyword=${keyword}`);

              clearTimeout(statusTimer);
              setStatusMessage('Finishing & formatting assets...');
              await new Promise(resolve => setTimeout(resolve, 600));

              setData(response.data || { results: [], market_average: "$0.00", total_found: 0, legit_count: 0 });
              setActiveTab('all');
            } catch (error) {
              clearTimeout(statusTimer);
              console.error("Error:", error);
              alert("System Offline");
            } finally {
              setLoading(false);
              setStatusMessage('');
            }
          }} className="mt-10 flex gap-3 justify-center max-w-2xl mx-auto relative">
            <div className="relative w-full">
              <input
                type="text"
                value={keyword}
                placeholder="Search for tech products (e.g. RTX 4090, M3 Macbook Air)..."
                className={`w-full border p-4 pl-6 rounded-2xl focus:ring-2 focus:ring-red-500 outline-none transition-all font-medium backdrop-blur-sm shadow-xl ${darkMode
                  ? 'bg-slate-900/60 border-slate-800/80 text-slate-200 placeholder:text-slate-600 focus:border-red-300'
                  : 'bg-white/80 border-slate-200 text-slate-800 placeholder:text-slate-400 focus:border-red-500'
                  }`}
                onChange={(e) => setKeyword(e.target.value)}
              />
            </div>
            <button
              disabled={loading}
              className="bg-red-600 hover:bg-red-500 active:scale-[0.98] text-white px-7 rounded-2xl font-bold flex items-center gap-2 transition-all disabled:opacity-50 shadow-lg shadow-white-600/20 shrink-0"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <Search size={20} />}
              <span>Analyze</span>
            </button>
          </form>

          {/* Progress Loading Bar - Repositioned for optimal visual hierarchy */}
          {loading && (
            <div className="max-w-2xl mx-auto mt-8 text-left">
              <div className="flex justify-between items-center mb-2.5 text-xs font-bold tracking-wide uppercase">
                <span className="flex items-center gap-2 text-indigo-500">
                  <Loader2 className="animate-spin text-amber-500" size={14} />
                  {statusMessage}
                </span>
                <span className={`font-mono ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                  {statusMessage.includes('Searching') && '35%'}
                  {statusMessage.includes('Analyzing') && '75%'}
                  {statusMessage.includes('Finishing') && '95%'}
                </span>
              </div>

              <div className={`w-full rounded-full h-2 overflow-hidden p-[1px] border ${darkMode ? 'bg-slate-950 border-slate-900' : 'bg-slate-200/60 border-slate-300/40'
                }`}>
                <div
                  className="h-full bg-gradient-to-r from-amber-500 via-orange-500 to-indigo-600 rounded-full transition-all duration-700 ease-out shadow-sm"
                  style={{
                    width: statusMessage.includes('Searching') ? '35%' :
                      statusMessage.includes('Analyzing') ? '75%' :
                        statusMessage.includes('Finishing') ? '98%' : '0%'
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Global Analytics Overview Panel */}
        {data?.results?.length > 0 && !loading && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-12">
            <div className={`border p-5 rounded-2xl flex items-center gap-4 backdrop-blur-sm ${darkMode ? 'bg-slate-900/40 border-slate-800/60' : 'bg-white border-slate-200 shadow-sm'}`}>
              <div className="bg-indigo-500/10 p-3 rounded-xl text-indigo-500 border border-indigo-500/10">
                <BarChart3 size={22} />
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Indexed Clean Average</p>
                <p className={`text-2xl font-black mt-0.5 ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                  {formatCurrency(data?.market_average)}
                </p>
              </div>
            </div>

            <div className={`border p-5 rounded-2xl flex items-center gap-4 backdrop-blur-sm ${darkMode ? 'bg-slate-900/40 border-slate-800/60' : 'bg-white border-slate-200 shadow-sm'}`}>
              <div className="bg-emerald-500/10 p-3 rounded-xl text-emerald-500 border border-emerald-500/10">
                <ShieldCheck size={22} />
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Legitimate Devices</p>
                <p className={`text-2xl font-black mt-0.5 ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                  {data?.legit_count || 0} <span className="text-xs font-medium text-slate-400">verified</span>
                </p>
              </div>
            </div>

            <div className={`border p-5 rounded-2xl flex items-center gap-4 backdrop-blur-sm ${darkMode ? 'bg-slate-900/40 border-slate-800/60' : 'bg-white border-slate-200 shadow-sm'}`}>
              <div className="bg-violet-500/10 p-3 rounded-xl text-violet-500 border border-violet-500/10">
                <Layers size={22} />
              </div>
              <div>
                <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Total Listings Processed</p>
                <p className={`text-2xl font-black mt-0.5 ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                  {data?.total_found || 0} <span className="text-xs font-medium text-slate-400">items</span>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Platform Origin Filter Tabs */}
        {data?.results?.length > 0 && !loading && (
          <div className={`flex items-center gap-2 mb-8 overflow-x-auto pb-2 border-b ${darkMode ? 'border-slate-900' : 'border-slate-200'}`}>
            {availableSources.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-2 rounded-xl text-xs font-bold capitalize transition-all border ${activeTab === tab
                  ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white border-indigo-500 shadow-md shadow-indigo-600/10'
                  : darkMode
                    ? 'bg-slate-900/60 text-slate-400 border-slate-800/80 hover:text-slate-200'
                    : 'bg-white text-slate-500 border-slate-200 hover:text-slate-800 shadow-sm'
                  }`}
              >
                {tab}
              </button>
            ))}
          </div>
        )}

        {/* Dynamic Card Architecture Grid */}
        {!loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredResults.map((product, index) => {
              const analysis = {
                // 1. Map to "ai_status" from Postman
                status: product?.ai_status || 'Unknown',

                // 2. Map to "ai_deal" from Postman
                badge: product?.ai_deal || 'Standard',

                // 3. Fallback or derive a score based on the deal type until backend sends it
                value_score: Number(product?.value_score) || (
                  product?.ai_deal?.includes('Steal') ? 90 :
                    product?.ai_deal?.includes('Fair') ? 70 :
                      product?.ai_deal?.includes('Premium') ? 40 : 50
                ),

                // 4. Generate a quick frontend opinion based on the deal text for now
                opinion: product?.opinion || `This item is flagged as a ${product?.ai_deal || 'Normal Deal'} and its legitimacy status is verified as ${product?.ai_status || 'unconfirmed'}.`
              };

              const isFlagged = analysis.status.includes('Flagged') || analysis.status.includes('🚩');

              return (
                <div
                  key={index}
                  className={`border rounded-2xl overflow-hidden flex flex-col justify-between transition-all duration-300 backdrop-blur-sm hover:-translate-y-0.5 ${isFlagged
                    ? 'border-rose-500/20 hover:border-rose-500/40 bg-rose-950/5'
                    : darkMode
                      ? 'bg-slate-900/20 border-slate-800/60 hover:border-slate-700 hover:shadow-xl'
                      : 'bg-white border-slate-200 shadow-sm hover:border-slate-300 hover:shadow-md'
                    }`}
                >
                  <div>
                    {/* Media Window */}
                    <div className={`relative h-52 p-6 flex items-center justify-center overflow-hidden border-b ${darkMode ? 'bg-white/[0.02] border-slate-900' : 'bg-slate-100/50 border-slate-200'
                      }`}>
                      <img
                        src={product?.image || "https://via.placeholder.com/150"}
                        className={`h-full object-contain opacity-95 transition-transform duration-500 ${darkMode ? 'mix-blend-lighten' : 'mix-blend-multiply'
                          }`}
                        alt={product?.title || 'Product'}
                      />
                      <div className={`absolute top-3.5 left-3.5 backdrop-blur-md text-[9px] font-black px-2.5 py-1 rounded-lg border uppercase tracking-wider ${darkMode ? 'bg-slate-950/80 border-slate-800 text-slate-300' : 'bg-white/90 border-slate-200 text-slate-600 shadow-sm'
                        }`}>
                        {product?.source || 'unknown'}
                      </div>
                      <div className={`absolute top-3.5 right-3.5 text-[10px] font-extrabold px-2.5 py-1 rounded-lg shadow-xl border ${getValueScoreColor(analysis.value_score)}`}>
                        {analysis.badge}
                      </div>
                    </div>

                    {/* Content Details */}
                    <div className="p-5 pb-2">
                      <h3 className={`font-semibold text-sm line-clamp-2 leading-relaxed h-10 ${darkMode ? 'text-slate-200' : 'text-slate-800'}`}>
                        {product?.title || ''}
                      </h3>

                      {/* Dynamic AI Technical Spec Tags */}
                      <div className="flex flex-wrap gap-1.5 mt-3 min-h-6">
                        {analysis.specs?.cpu && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-500 border border-indigo-500/10">{analysis.specs.cpu}</span>
                        )}
                        {analysis.specs?.ram && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-500 border border-blue-500/10">{analysis.specs.ram}</span>
                        )}
                        {analysis.specs?.storage && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-400 border border-violet-500/10">{analysis.specs.storage}</span>
                        )}
                      </div>

                      <div className="flex items-baseline gap-2 mt-4">
                        <span className={`text-2xl font-black tracking-tight ${darkMode ? 'text-white' : 'text-slate-900'}`}>
                          {formatCurrency(product?.price)}
                        </span>
                      </div>

                      {/* Value Analysis Interface Meter */}
                      <div className={`mt-4 pt-4 border-t ${darkMode ? 'border-slate-900' : 'border-slate-100'}`}>
                        <div className="flex justify-between items-center text-[10px] font-bold mb-1.5 text-slate-400">
                          <span className="uppercase tracking-wider flex items-center gap-1"><Info size={11} /> Value Score</span>
                          <span className={`font-mono ${darkMode ? 'text-slate-300' : 'text-slate-600'}`}>{analysis.value_score}/100</span>
                        </div>
                        <div className={`w-full rounded-full h-1.5 overflow-hidden border ${darkMode ? 'bg-slate-950 border-slate-900' : 'bg-slate-100 border-slate-200'}`}>
                          <div
                            className={`h-full transition-all duration-500 ${getValueBarColor(analysis.value_score)}`}
                            style={{ width: `${analysis.value_score}%` }}
                          />
                        </div>
                        <p className={`text-[11px] font-medium mt-2 leading-relaxed line-clamp-2 italic ${darkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                          "{analysis.opinion}"
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Action Row */}
                  <div className="p-5 pt-2">
                    <div className="mt-2 flex items-center justify-between">
                      <div className={`flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-lg border ${analysis.status.includes('Legit') ? 'bg-emerald-500/5 text-emerald-500 border-emerald-500/10' : 'bg-rose-500/5 text-rose-500 border-rose-500/10'
                        }`}>
                        {analysis.status.includes('Legit') ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                        {analysis.status}
                      </div>

                      <a
                        href={product?.link || '#'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={`flex items-center gap-1 text-[10px] font-bold transition-colors uppercase tracking-widest px-3 py-1.5 rounded-lg border ${darkMode ? 'text-indigo-400 hover:text-indigo-300 bg-slate-950 border-slate-900' : 'text-indigo-600 hover:text-indigo-700 bg-slate-50 border-slate-200 shadow-sm'
                          }`}
                      >
                        View Link <ExternalLink size={11} />
                      </a>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Empty Search Prompt Base */}
        {(data?.results?.length === 0 || !data?.results) && !loading && (
          <div className={`text-center py-28 border border-dashed rounded-3xl max-w-3xl mx-auto mt-6 backdrop-blur-sm ${darkMode ? 'border-slate-800/80 bg-slate-900/10' : 'border-slate-300 bg-white shadow-sm'
            }`}>
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-5 border ${darkMode ? 'bg-slate-900/60 border-slate-800 text-slate-500' : 'bg-slate-50 border-slate-200 text-slate-400'
              }`}>
              <ShoppingCart size={24} />
            </div>
            <h3 className={`text-lg font-bold mb-1 ${darkMode ? 'text-slate-200' : 'text-slate-800'}`}>Analytical Sandbox Empty</h3>
            <p className={`text-xs max-w-xs mx-auto leading-relaxed ${darkMode ? 'text-slate-500' : 'text-slate-400'}`}>
              Input a focal target parameter keyword into the analyzer cluster above to trigger live system loops.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;