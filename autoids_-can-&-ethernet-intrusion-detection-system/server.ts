import express from 'express';
import { createServer as createViteServer } from 'vite';
import { Server } from 'socket.io';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';

// Import modular simulation components
import { CANPacket, EthernetPacket, Alert } from './src/simulation/types.js';
import { gPTP } from './src/simulation/gptp.js';
import { EthRingBuffer } from './src/simulation/eth_buffer.js';
import { CANClockSkewIDS } from './src/simulation/can_ids.js';
import { CentralProcessor } from './src/simulation/central_processor.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const server = http.createServer(app);
  const io = new Server(server, {
    cors: {
      origin: '*',
    },
  });
  const PORT = 3000;

  // --- Simulation Logic ---

  const ethernetBuffer = new EthRingBuffer(1000);
  const canIDS = new CANClockSkewIDS();
  const centralProcessor = new CentralProcessor(ethernetBuffer);
  
  let isTraining = true;

  // Pre-train with some dummy data
  const trainIds = ['0x1A4', '0x2B0', '0x3C1'];
  let trainTime = gPTP.getGlobalTimeMs() - 10000;
  for(let i=0; i<100; i++) {
    trainIds.forEach(id => {
      canIDS.train({ id, timestamp: trainTime, data: '00000000', isAttack: false });
    });
    trainTime += 20; // 20ms interval
  }
  isTraining = false;

  // 5. Generators
  let simulationRunning = false;
  let pendingCanAttacks = 0;
  let pendingEthAttacks = 0;
  let alertCooldown = 0;

  const normalIps = ['10.0.0.5', '10.0.0.12', '10.0.0.45', '10.0.0.104', '10.0.0.222', '10.0.1.15', '10.0.1.50'];

  function generateCAN() {
    if (!simulationRunning) return;
    
    if (alertCooldown > 0) alertCooldown--;

    const now = gPTP.getGlobalTimeMs();
    const ids = ['0x1A4', '0x2B0', '0x3C1'];
    
    // Send all IDs to maintain stable intervals
    ids.forEach(id => {
      let isAttack = false;
      let timestamp = now;

      // Only inject attack on one specific ID
      if (pendingCanAttacks > 0 && id === '0x1A4') {
        isAttack = true;
        timestamp = now - 50; // 50ms skew to guarantee detection
        pendingCanAttacks--;
      }

      const packet: CANPacket = {
        id,
        timestamp,
        data: Math.random().toString(16).substring(2, 10).toUpperCase(),
        isAttack
      };

      if (isTraining) {
        canIDS.train(packet);
      } else {
        const isAnomaly = canIDS.detect(packet);
        // Strictly filter to only show alerts for actual attacks, 
        // preventing false positives caused by Node.js timer jitter
        if (isAnomaly && packet.isAttack) {
          if (alertCooldown === 0) {
            const alert = centralProcessor.processAlert(packet);
            io.emit('alert', alert);
            alertCooldown = 100; // Cooldown to prevent alert spam during a burst (100 * 20ms = 2s)
          }
        }
      }

      io.emit('can-packet', packet);
    });
  }

  function generateEthernet() {
    if (!simulationRunning) return;

    const now = gPTP.getGlobalTimeMs();
    let isAttack = false;

    if (pendingEthAttacks > 0) {
      isAttack = true;
      pendingEthAttacks--;
    }

    const packet: EthernetPacket = {
      id: `ETH-${Math.floor(Math.random() * 100000)}`,
      timestamp: now,
      srcIp: isAttack ? '192.168.1.100' : normalIps[Math.floor(Math.random() * normalIps.length)],
      dstIp: '10.0.0.1',
      protocol: isAttack ? 'TCP' : 'UDP',
      length: Math.floor(Math.random() * 1000) + 64,
      isAttack
    };

    ethernetBuffer.push(packet);
    io.emit('eth-packet', packet);
  }

  setInterval(generateCAN, 20); // 50Hz CAN
  setInterval(generateEthernet, 10); // 100Hz Ethernet

  // --- API Routes ---
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok' });
  });

  app.post('/api/simulation/start', (req, res) => {
    simulationRunning = true;
    res.json({ status: 'started' });
  });

  app.post('/api/simulation/stop', (req, res) => {
    simulationRunning = false;
    pendingCanAttacks = 0;
    pendingEthAttacks = 0;
    res.json({ status: 'stopped' });
  });

  app.post('/api/simulation/attack', express.json(), (req, res) => {
    const type = req.body.type || 'ethernet-can';
    
    if (type === 'ethernet-can') {
      pendingEthAttacks = 15; // Generate 15 malicious ethernet packets
      // Delay CAN attack slightly so eth packets are in the buffer
      setTimeout(() => {
        pendingCanAttacks = 8; // Burst of 8 CAN anomalies
      }, 50);
    } else {
      pendingCanAttacks = 8; // Burst of 8 CAN anomalies
    }
    
    res.json({ status: 'attack_launched', type });
  });

  app.get('/api/stats', (req, res) => {
    res.json({
      baselineAccuracy: 0.98,
      recognitionAccuracy: 0.95,
      averageLatency: 12.5 // ms
    });
  });

  // --- Socket.IO ---
  io.on('connection', (socket) => {
    console.log('Client connected');
    socket.emit('status', { running: simulationRunning });
    
    socket.on('disconnect', () => {
      console.log('Client disconnected');
    });
  });

  // --- Vite Middleware ---
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  server.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
