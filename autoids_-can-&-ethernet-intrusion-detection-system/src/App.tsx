import React, { useEffect, useState, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { 
  Activity, ShieldAlert, ShieldCheck, Cpu, Network, 
  Play, Square, Zap, Database, Clock, AlertTriangle 
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ScatterChart, Scatter, ZAxis
} from 'recharts';
import { format } from 'date-fns';

// --- Types ---
interface CANPacket {
  id: string;
  timestamp: number;
  data: string;
  isAttack: boolean;
}

interface EthernetPacket {
  id: string;
  timestamp: number;
  srcIp: string;
  dstIp: string;
  protocol: string;
  length: number;
  isAttack: boolean;
}

interface Alert {
  id: string;
  timestamp: number;
  canPacket: CANPacket;
  ethernetContext: EthernetPacket[];
  classification: string;
  confidence: number;
}

export default function App() {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  
  // Data states
  const [canPackets, setCanPackets] = useState<CANPacket[]>([]);
  const [ethPackets, setEthPackets] = useState<EthernetPacket[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [stats, setStats] = useState({ baselineAccuracy: 0, recognitionAccuracy: 0, averageLatency: 0 });

  // Refs for performance
  const canRef = useRef<CANPacket[]>([]);
  const ethRef = useRef<EthernetPacket[]>([]);

  useEffect(() => {
    const newSocket = io();
    setSocket(newSocket);

    newSocket.on('status', (data) => setIsRunning(data.running));
    
    newSocket.on('can-packet', (packet: CANPacket) => {
      canRef.current = [...canRef.current.slice(-50), packet];
      setCanPackets([...canRef.current]);
    });

    newSocket.on('eth-packet', (packet: EthernetPacket) => {
      ethRef.current = [...ethRef.current.slice(-50), packet];
      setEthPackets([...ethRef.current]);
    });

    newSocket.on('alert', (alert: Alert) => {
      setAlerts(prev => [alert, ...prev].slice(0, 10));
      // Delay the modal popup by 2 seconds so the user can observe 
      // the red dots and highlighted streams first
      setTimeout(() => {
        setSelectedAlert(alert);
      }, 2000);
    });

    fetch('/api/stats')
      .then(res => res.json())
      .then(data => setStats(data));

    return () => {
      newSocket.disconnect();
    };
  }, []);

  const toggleSimulation = async () => {
    const endpoint = isRunning ? '/api/simulation/stop' : '/api/simulation/start';
    await fetch(endpoint, { method: 'POST' });
    setIsRunning(!isRunning);
  };

  const launchAttack = async (type: string) => {
    await fetch('/api/simulation/attack', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type })
    });
  };

  // Chart data formatting
  const skewData = canPackets.map((p, i) => ({
    index: i,
    skew: p.isAttack ? Math.random() * 10 + 5 : Math.random() * 2,
    isAttack: p.isAttack
  }));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-4 font-sans">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-8 h-8 text-emerald-500" />
          <h1 className="text-2xl font-bold tracking-tight text-white">AutoIDS Dashboard</h1>
          <span className="px-2 py-1 text-xs font-medium bg-slate-800 rounded-md text-slate-400">
            CAN + Ethernet Fusion
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="relative flex h-3 w-3">
              {isRunning && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
              <span className={`relative inline-flex rounded-full h-3 w-3 ${isRunning ? 'bg-emerald-500' : 'bg-slate-600'}`}></span>
            </span>
            {isRunning ? 'System Active' : 'System Offline'}
          </div>
          <button 
            onClick={toggleSimulation}
            className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
              isRunning ? 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20' : 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20'
            }`}
          >
            {isRunning ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isRunning ? 'Stop Simulation' : 'Start Simulation'}
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Controls & Stats */}
        <div className="lg:col-span-3 space-y-6">
          {/* Attack Controls */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4" /> Threat Simulation
            </h2>
            <div className="space-y-3">
              <button 
                onClick={() => launchAttack('ethernet-can')}
                disabled={!isRunning}
                className="w-full flex items-center justify-between px-4 py-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors border border-slate-700"
              >
                <span className="font-medium text-sm">Ethernet → CAN Attack</span>
                <Network className="w-4 h-4 text-orange-400" />
              </button>
              <button 
                onClick={() => launchAttack('can-internal')}
                disabled={!isRunning}
                className="w-full flex items-center justify-between px-4 py-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors border border-slate-700"
              >
                <span className="font-medium text-sm">Internal CAN Injection</span>
                <Cpu className="w-4 h-4 text-rose-400" />
              </button>
            </div>
          </div>

          {/* Performance Metrics */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4" /> System Performance
            </h2>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-400">Baseline Accuracy</span>
                  <span className="text-emerald-400 font-mono">{(stats.baselineAccuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500" style={{ width: `${stats.baselineAccuracy * 100}%` }}></div>
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-400">ML Recognition</span>
                  <span className="text-blue-400 font-mono">{(stats.recognitionAccuracy * 100).toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500" style={{ width: `${stats.recognitionAccuracy * 100}%` }}></div>
                </div>
              </div>
              <div className="pt-2 border-t border-slate-800 flex justify-between items-center">
                <span className="text-sm text-slate-400">Processing Latency</span>
                <span className="text-lg font-mono text-white">{stats.averageLatency} <span className="text-xs text-slate-500">ms</span></span>
              </div>
            </div>
          </div>
        </div>

        {/* Middle Column: Visualizations */}
        <div className="lg:col-span-6 space-y-6">
          {/* Clock Skew Chart */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-[300px] flex flex-col">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Clock className="w-4 h-4" /> CAN Clock Skew Detection
            </h2>
            <div className="flex-1 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 10, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="index" type="number" hide />
                  <YAxis dataKey="skew" type="number" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <ZAxis range={[20, 20]} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                    itemStyle={{ color: '#f8fafc' }}
                  />
                  <Scatter 
                    data={skewData.filter(d => !d.isAttack)} 
                    fill="#3b82f6" 
                    opacity={0.6}
                  />
                  <Scatter 
                    data={skewData.filter(d => d.isAttack)} 
                    fill="#ef4444" 
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Data Streams */}
          <div className="grid grid-cols-2 gap-4">
            {/* CAN Stream */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase mb-3 flex items-center gap-2">
                <Cpu className="w-3 h-3" /> CAN Bus Stream
              </h3>
              <div className="space-y-1 h-[200px] overflow-hidden flex flex-col justify-end">
                {canPackets.slice(-8).map((p, i) => (
                  <div key={i} className={`text-xs font-mono p-1.5 rounded flex justify-between ${p.isAttack ? 'bg-rose-500/20 text-rose-400' : 'text-slate-400'}`}>
                    <span>{p.id}</span>
                    <span>{p.data}</span>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Ethernet Stream */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h3 className="text-xs font-semibold text-slate-400 uppercase mb-3 flex items-center gap-2">
                <Database className="w-3 h-3" /> Ethernet Ring Buffer
              </h3>
              <div className="space-y-1 h-[200px] overflow-hidden flex flex-col justify-end">
                {ethPackets.slice(-8).map((p, i) => (
                  <div key={i} className={`text-xs font-mono p-1.5 rounded flex justify-between ${p.isAttack ? 'bg-orange-500/20 text-orange-400' : 'text-slate-400'}`}>
                    <span>{p.protocol}</span>
                    <span className="truncate max-w-[100px]">{p.srcIp}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Alerts & Central Processor */}
        <div className="lg:col-span-3">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 h-full flex flex-col">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4" /> Central Processor Alerts
            </h2>
            
            <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
              {alerts.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-2">
                  <ShieldCheck className="w-8 h-8 opacity-50" />
                  <span className="text-sm">No threats detected</span>
                </div>
              ) : (
                alerts.map((alert, i) => (
                  <div key={alert.id} className="bg-slate-800/50 border border-rose-500/30 rounded-lg p-3 animate-in fade-in slide-in-from-right-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-xs font-bold text-rose-400 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> {alert.classification}
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {format(alert.timestamp, 'HH:mm:ss.SSS')}
                      </span>
                    </div>
                    <div className="text-xs text-slate-300 space-y-1 mb-2">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Confidence:</span>
                        <span className="font-mono text-blue-400">{(alert.confidence * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Trigger ID:</span>
                        <span className="font-mono">{alert.canPacket.id}</span>
                      </div>
                    </div>
                    <div className="mt-2 pt-2 border-t border-slate-700">
                      <span className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1">Context Captured</span>
                      <span className="text-xs font-mono text-slate-400">
                        {alert.ethernetContext.length} ETH packets buffered
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>

      {/* Attack Details Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-rose-500/50 rounded-xl p-6 max-w-2xl w-full shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex justify-between items-start mb-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-rose-500/20 rounded-lg">
                  <AlertTriangle className="w-6 h-6 text-rose-500" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Intrusion Detected</h2>
                  <p className="text-sm text-slate-400 font-mono">{selectedAlert.id}</p>
                </div>
              </div>
              <button 
                onClick={() => setSelectedAlert(null)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <Square className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Classification</span>
                <span className="text-sm font-bold text-rose-400">{selectedAlert.classification}</span>
              </div>
              <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                <span className="text-xs text-slate-500 uppercase tracking-wider block mb-1">ML Confidence</span>
                <span className="text-sm font-bold text-blue-400">{(selectedAlert.confidence * 100).toFixed(2)}%</span>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-300 mb-2 border-b border-slate-800 pb-1">Trigger: CAN Packet</h3>
                <div className="bg-slate-950 rounded-md p-3 font-mono text-xs text-slate-400 border border-slate-800">
                  <div className="flex justify-between mb-1">
                    <span className="text-slate-500">Timestamp:</span>
                    <span>{format(selectedAlert.canPacket.timestamp, 'HH:mm:ss.SSS')}</span>
                  </div>
                  <div className="flex justify-between mb-1">
                    <span className="text-slate-500">ID:</span>
                    <span className="text-rose-400">{selectedAlert.canPacket.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Payload:</span>
                    <span>{selectedAlert.canPacket.data}</span>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-slate-300 mb-2 border-b border-slate-800 pb-1">Context: Ethernet Ring Buffer</h3>
                <div className="bg-slate-950 rounded-md p-3 font-mono text-xs text-slate-400 border border-slate-800 max-h-[150px] overflow-y-auto custom-scrollbar">
                  {selectedAlert.ethernetContext.length === 0 ? (
                    <span className="text-slate-600 italic">No Ethernet context found in timeframe.</span>
                  ) : (
                    <table className="w-full text-left">
                      <thead>
                        <tr className="text-slate-500 border-b border-slate-800">
                          <th className="pb-1 font-normal">Time</th>
                          <th className="pb-1 font-normal">Proto</th>
                          <th className="pb-1 font-normal">Src IP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedAlert.ethernetContext.map((eth, idx) => (
                          <tr key={idx} className={eth.isAttack ? 'text-orange-400' : ''}>
                            <td className="py-1">{format(eth.timestamp, 'ss.SSS')}</td>
                            <td className="py-1">{eth.protocol}</td>
                            <td className="py-1">{eth.srcIp}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button 
                onClick={() => setSelectedAlert(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-md transition-colors text-sm font-medium"
              >
                Acknowledge
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

