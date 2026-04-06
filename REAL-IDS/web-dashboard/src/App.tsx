import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react';

const ETH_RING = 10;
/** Ring UI width; daemon keeps up to 128 CAN frames for ML sliding windows */
const CAN_RING = 64;

function baseUrl(): string {
  const u = import.meta.env.VITE_REAL_IDS_URL || '';
  return u.replace(/\/$/, '');
}

interface CanPacket {
  id: string;
  timestamp: number;
  data: string;
  isAttack?: boolean;
}

interface EthPacket {
  id: string;
  timestamp: number;
  srcIp: string;
  dstIp: string;
  protocol: string;
  length: number;
  isAttack?: boolean;
}

interface ChainStep {
  order: number;
  stage: string;
  detail: string;
}

interface MlFusion {
  fusion_attack_type?: string;
  fusion_summary?: string;
  attack_chain?: ChainStep[];
  ethernet_ml?: {
    label?: string;
    probability_anomaly?: number;
    source?: string;
    note?: string;
  };
  can_ml?: {
    class_id?: number;
    class_name?: string;
    confidence?: number;
    class_probs?: Record<string, number>;
  };
  can_class_names?: string[];
  eth_model_note?: string;
  /** Cross-domain attack-chain Transformer (T=10), when CHAIN_* weights loaded */
  attack_chain_ml?: Record<string, unknown>;
}

interface AlertPayload {
  id: string;
  timestamp: number;
  canPacket: CanPacket;
  ethernetContext: EthPacket[];
  classification: string;
  confidence: number;
  ml_fusion?: MlFusion;
}

function RingSlots({
  label,
  capacity,
  items,
  attackKey,
}: {
  label: string;
  capacity: number;
  items: { isAttack?: boolean }[];
  attackKey: string;
}) {
  const slots = useMemo(() => {
    const arr: ({ isAttack?: boolean } | null)[] = Array(capacity).fill(null);
    const slice = items.slice(-capacity);
    const start = capacity - slice.length;
    slice.forEach((it, i) => {
      arr[start + i] = it;
    });
    return arr;
  }, [items, capacity]);

  const radius = capacity > 12 ? 72 : 56;
  const step = 360 / capacity;

  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label} · 容量 {capacity}（最旧→最新顺时针）
      </div>
      <div
        style={{
          position: 'relative',
          width: radius * 2 + 48,
          height: radius * 2 + 48,
          margin: '0 auto',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: radius * 2,
            height: radius * 2,
            marginLeft: -radius,
            marginTop: -radius,
            borderRadius: '50%',
            border: '1px dashed var(--border)',
            opacity: 0.6,
          }}
        />
        {slots.map((cell, i) => {
          const rad = ((i * step - 90) * Math.PI) / 180;
          const x = radius + Math.cos(rad) * (radius - 8);
          const y = radius + Math.sin(rad) * (radius - 8);
          const filled = cell != null;
          const atk = filled && cell!.isAttack;
          return (
            <div
              key={i}
              title={`槽 ${i}${filled ? ' 有数据' : ' 空'}`}
              style={{
                position: 'absolute',
                left: x - 6 + 24,
                top: y - 6 + 24,
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: !filled ? '#1e293b' : atk ? 'var(--danger)' : 'var(--accent)',
                border: `1px solid ${filled ? (atk ? '#fecaca' : '#7dd3fc') : 'var(--border)'}`,
                boxShadow: filled ? '0 0 8px rgba(56,189,248,0.25)' : 'none',
              }}
            />
          );
        })}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%,-50%)',
            fontSize: '0.65rem',
            color: 'var(--muted)',
            textAlign: 'center',
            maxWidth: radius * 1.4,
            lineHeight: 1.3,
          }}
        >
          环形缓冲
          <br />
          <span className="mono">{attackKey}</span>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const api = baseUrl();
  const [connected, setConnected] = useState(false);
  const [simRunning, setSimRunning] = useState(false);
  const [canBuf, setCanBuf] = useState<CanPacket[]>([]);
  const [ethBuf, setEthBuf] = useState<EthPacket[]>([]);
  const [alerts, setAlerts] = useState<AlertPayload[]>([]);
  const [selected, setSelected] = useState<AlertPayload | null>(null);
  const [stats, setStats] = useState<{ subscribers?: number }>({});
  const [lastError, setLastError] = useState<string | null>(null);

  const pushCan = useCallback((p: CanPacket) => {
    setCanBuf((prev) => [...prev.slice(-(CAN_RING * 2 - 1)), p].slice(-CAN_RING));
  }, []);

  const pushEth = useCallback((p: EthPacket) => {
    setEthBuf((prev) => [...prev.slice(-(ETH_RING * 2 - 1)), p].slice(-ETH_RING));
  }, []);

  useEffect(() => {
    if (!api) {
      setLastError('未配置 VITE_REAL_IDS_URL，请复制 .env.example 为 .env 并填写 daemon 地址');
      return;
    }

    let es: EventSource | null = null;
    try {
      es = new EventSource(`${api}/api/v1/stream`);
    } catch (e) {
      setLastError(String(e));
      return;
    }

    es.onopen = () => {
      setConnected(true);
      setLastError(null);
    };
    es.onerror = () => {
      setConnected(false);
    };

    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as { event: string; payload: unknown };
        if (msg.event === 'can-packet') pushCan(msg.payload as CanPacket);
        if (msg.event === 'eth-packet') pushEth(msg.payload as EthPacket);
        if (msg.event === 'alert') {
          const a = msg.payload as AlertPayload;
          setAlerts((prev) => [a, ...prev].slice(0, 20));
          setSelected(a);
        }
        if (msg.event === 'status') {
          const p = msg.payload as { running?: boolean };
          if (typeof p.running === 'boolean') setSimRunning(p.running);
        }
      } catch {
        /* ignore */
      }
    };

    return () => es?.close();
  }, [api, pushCan, pushEth]);

  useEffect(() => {
    if (!api) return;
    fetch(`${api}/api/v1/stats`)
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {});
  }, [api]);

  const post = async (path: string, body?: object) => {
    if (!api) return;
    await fetch(`${api}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
  };

  return (
    <div style={{ padding: '1rem 1.25rem', maxWidth: 1400, margin: '0 auto' }}>
      <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>REAL-IDS Observatory</h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', color: 'var(--muted)' }}>
            环形缓冲 · 分类 · 攻击链（<span className="mono">ml_fusion</span>）
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: connected ? 'var(--ok)' : 'var(--danger)',
            }}
          />
          SSE {connected ? '已连接' : '未连接'}
          {api && (
            <span className="mono" style={{ color: 'var(--muted)' }}>
              {api}
            </span>
          )}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={async () => {
              await post(simRunning ? '/api/v1/simulation/stop' : '/api/v1/simulation/start');
              setSimRunning(!simRunning);
            }}
            style={btnStyle(simRunning)}
          >
            {simRunning ? '停止仿真' : '启动仿真'}
          </button>
          <button type="button" onClick={() => post('/api/v1/simulation/attack', { type: 'ethernet-can' })} style={btnStyle(false, 'warn')}>
            攻击: Ethernet→CAN
          </button>
          <button type="button" onClick={() => post('/api/v1/simulation/attack', { type: 'can-internal' })} style={btnStyle(false, 'warn')}>
            攻击: 仅 CAN
          </button>
        </div>
      </header>

      {lastError && (
        <div style={{ background: 'rgba(248,113,113,0.12)', border: '1px solid var(--danger)', padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem', fontSize: '0.9rem' }}>
          {lastError}
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '1rem',
          alignItems: 'start',
        }}
      >
        {/* Left: streams */}
        <div style={panelStyle}>
          <h2 style={h2Style}>数据流</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <div style={subTitle}>CAN（最近 {CAN_RING} 帧）</div>
              <div style={streamBox}>
                {canBuf
                  .slice()
                  .reverse()
                  .slice(0, 12)
                  .map((p, i) => (
                    <div key={i} style={{ ...rowStyle, borderLeft: p.isAttack ? '3px solid var(--danger)' : '3px solid transparent' }}>
                      <span className="mono">{p.id}</span>
                      <span className="mono" style={{ color: 'var(--muted)' }}>
                        {p.data}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
            <div>
              <div style={subTitle}>Ethernet（最近 {ETH_RING} 帧）</div>
              <div style={streamBox}>
                {ethBuf
                  .slice()
                  .reverse()
                  .slice(0, 12)
                  .map((p, i) => (
                    <div key={i} style={{ ...rowStyle, borderLeft: p.isAttack ? '3px solid var(--warn)' : '3px solid transparent' }}>
                      <span>{p.protocol}</span>
                      <span className="mono" style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>
                        {p.srcIp}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
          <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
            统计: SSE 订阅者约 {stats.subscribers ?? '—'}（来自 <span className="mono">/api/v1/stats</span>）
          </div>
        </div>

        {/* Center: rings */}
        <div style={panelStyle}>
          <h2 style={h2Style}>环形存储示意</h2>
          <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 0 }}>
            与 daemon 内 EthRingBuffer(1000) 不同；此处仅展示最近 {ETH_RING}/{CAN_RING} 条用于观测对齐。
          </p>
          <RingSlots label="车载以太网（展示窗）" capacity={ETH_RING} items={ethBuf} attackKey="eth_buf" />
          <RingSlots label="CAN 时间窗（对齐 ML 29 帧）" capacity={CAN_RING} items={canBuf} attackKey="can_hist" />
        </div>

        {/* Right: alerts + chain */}
        <div style={panelStyle}>
          <h2 style={h2Style}>告警与融合</h2>
          <div style={{ maxHeight: 220, overflowY: 'auto', marginBottom: '1rem' }}>
            {alerts.length === 0 ? (
              <p style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>暂无告警。先启动仿真再注入攻击。</p>
            ) : (
              alerts.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setSelected(a)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '0.5rem 0.65rem',
                    marginBottom: 6,
                    borderRadius: 6,
                    border: selected?.id === a.id ? '1px solid var(--accent)' : '1px solid var(--border)',
                    background: selected?.id === a.id ? 'rgba(56,189,248,0.08)' : 'var(--bg)',
                    color: 'var(--text)',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                  }}
                >
                  <div className="mono" style={{ color: 'var(--danger)' }}>
                    {a.classification}
                  </div>
                  <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{a.id}</div>
                </button>
              ))
            )}
          </div>

          {selected && <AlertDetail alert={selected} />}
        </div>
      </div>
    </div>
  );
}

function AlertDetail({ alert }: { alert: AlertPayload }) {
  const m = alert.ml_fusion;
  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>规则融合（REAL-IDS）</h3>
      <div style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>
        <div>
          <span style={{ color: 'var(--muted)' }}>classification</span>{' '}
          <span className="mono" style={{ color: 'var(--danger)' }}>
            {alert.classification}
          </span>
        </div>
        <div>
          <span style={{ color: 'var(--muted)' }}>confidence</span> <span className="mono">{(alert.confidence * 100).toFixed(1)}%</span>
        </div>
      </div>

      <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem' }}>触发 CAN</h3>
      <pre style={preStyle}>{JSON.stringify(alert.canPacket, null, 2)}</pre>

      <h3 style={{ margin: '1rem 0 0.5rem', fontSize: '0.95rem' }}>融合窗内以太网上下文（{alert.ethernetContext?.length ?? 0} 条）</h3>
      <pre style={{ ...preStyle, maxHeight: 140 }}>{JSON.stringify(alert.ethernetContext, null, 2)}</pre>

      {m ? (
        <>
          <h3 style={{ margin: '1rem 0 0.5rem', fontSize: '0.95rem' }}>ML 桥接 · 攻击类型</h3>
          <p style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>{m.fusion_attack_type}</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{m.fusion_summary}</p>

          <h3 style={{ margin: '1rem 0 0.5rem', fontSize: '0.95rem' }}>分类结果</h3>
          <div style={{ fontSize: '0.82rem', display: 'grid', gap: '0.35rem' }}>
            <div>
              <span style={{ color: 'var(--muted)' }}>以太网 IntrusionDetectNet</span>
              <pre style={preStyle}>{JSON.stringify(m.ethernet_ml, null, 2)}</pre>
            </div>
            <div>
              <span style={{ color: 'var(--muted)' }}>CAN supervised（5 类）</span>
              <pre style={preStyle}>{JSON.stringify(m.can_ml, null, 2)}</pre>
            </div>
            {m.eth_model_note && <div style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>{m.eth_model_note}</div>}
          </div>

          <h3 style={{ margin: '1rem 0 0.5rem', fontSize: '0.95rem' }}>完整攻击链</h3>
          <ol style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.82rem', lineHeight: 1.55 }}>
            {(m.attack_chain || []).map((s) => (
              <li key={s.order} style={{ marginBottom: '0.5rem' }}>
                <span style={{ color: 'var(--accent)', textTransform: 'uppercase', fontSize: '0.7rem' }}>{s.stage}</span>
                <div>{s.detail}</div>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '1rem' }}>
          无 <span className="mono">ml_fusion</span>。若需显示攻击链与深度学习分类，请启动{' '}
          <span className="mono">integration/ml_bridge</span> 并设置环境变量{' '}
          <span className="mono">REAL_IDS_ML_BRIDGE</span> 后重启 daemon。
        </p>
      )}
    </div>
  );
}

const panelStyle: CSSProperties = {
  background: 'var(--panel)',
  border: '1px solid var(--border)',
  borderRadius: 12,
  padding: '1rem 1.1rem',
};

const h2Style: CSSProperties = {
  margin: '0 0 0.75rem',
  fontSize: '0.85rem',
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: 'var(--muted)',
};

const subTitle: CSSProperties = { fontSize: '0.72rem', color: 'var(--muted)', marginBottom: 6 };

const streamBox: CSSProperties = {
  background: 'var(--bg)',
  borderRadius: 8,
  border: '1px solid var(--border)',
  padding: 6,
  maxHeight: 220,
  overflowY: 'auto',
};

const rowStyle: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  gap: 8,
  padding: '4px 6px',
  fontSize: '0.75rem',
  borderRadius: 4,
  marginBottom: 2,
};

const preStyle: CSSProperties = {
  background: 'var(--bg)',
  padding: '0.5rem 0.65rem',
  borderRadius: 8,
  border: '1px solid var(--border)',
  fontSize: '0.72rem',
  overflow: 'auto',
  margin: '0.35rem 0 0',
};

function btnStyle(active: boolean, tone?: 'warn'): CSSProperties {
  const bg = tone === 'warn' ? 'rgba(251,191,36,0.12)' : active ? 'rgba(248,113,113,0.12)' : 'rgba(74,222,128,0.12)';
  const fg = tone === 'warn' ? 'var(--warn)' : active ? 'var(--danger)' : 'var(--ok)';
  return {
    padding: '0.45rem 0.85rem',
    borderRadius: 8,
    border: `1px solid ${fg}`,
    background: bg,
    color: fg,
    fontWeight: 600,
    fontSize: '0.8rem',
    cursor: 'pointer',
  };
}
