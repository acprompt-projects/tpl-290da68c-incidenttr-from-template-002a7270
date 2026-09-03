import React, { useState, useEffect } from 'react';

const API = 'http://localhost:8000';
const SEV_ORDER = ['critical','high','medium','low','info'];
const SEV_COLORS = {
  critical: {bg:'#fce4ec',border:'#c62828',text:'#b71c1c'},
  high:     {bg:'#fff3e0',border:'#e65100',text:'#bf360c'},
  medium:   {bg:'#fffde7',border:'#f9a825',text:'#f57f17'},
  low:      {bg:'#e3f2fd',border:'#1565c0',text:'#0d47a1'},
  info:     {bg:'#f3e5f5',border:'#7b1fa2',text:'#4a148c'},
};
const STATUS_COLORS = {
  new: '#c62828', investigating: '#e65100',
  resolved: '#2e7d32', suppressed: '#757575',
};
const MOCK = [
  {id:'INC-001',title:'DB connection pool exhausted',severity:'critical',status:'new',service:'payments-api',created_at:'2024-06-15T09:12:00Z',description:'Primary DB connection pool at 100% capacity. All payment processing blocked.',alerts_count:12,assigned_to:null},
  {id:'INC-002',title:'Elevated 5xx on auth service',severity:'high',status:'investigating',service:'auth-svc',created_at:'2024-06-15T09:05:00Z',description:'Error rate spiked to 15% on /token endpoint. Possible OIDC provider issue.',alerts_count:5,assigned_to:'oncall-platform'},
  {id:'INC-003',title:'Disk usage >90% on worker-03',severity:'medium',status:'new',service:'infra',created_at:'2024-06-15T08:44:00Z',description:'Worker node worker-03 disk at 92%. Log rotation may be stalled.',alerts_count:2,assigned_to:null},
  {id:'INC-004',title:'Latency spike on search cluster',severity:'low',status:'investigating',service:'search-svc',created_at:'2024-06-15T08:30:00Z',description:'P99 latency increased from 120ms to 450ms on search queries.',alerts_count:3,assigned_to:'oncall-search'},
  {id:'INC-005',title:'Stale config on edge proxies',severity:'info',status:'resolved',service:'cdn-edge',created_at:'2024-06-15T07:00:00Z',description:'Edge proxies serving cached config older than 24h. No user impact detected.',alerts_count:1,assigned_to:'team-infra'},
];

function fetchIncidents() {
  return fetch(`${API}/incidents`).then(r => r.json()).catch(() => MOCK);
}
function patchIncident(id, data) {
  return fetch(`${API}/incidents/${id}`, {
    method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)
  }).then(r => r.json()).catch(() => null);
}

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [sevFilter, setSevFilter] = useState(null);
  const [statusFilter, setStatusFilter] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchIncidents().then(d => { setIncidents(d); setLoading(false); }); }, []);

  const filtered = incidents.filter(i =>
    (!sevFilter || i.severity === sevFilter) &&
    (!statusFilter || i.status === statusFilter)
  );
  const selectedInc = selected ? incidents.find(i => i.id === selected) : null;

  const handleStatus = async (id, status) => {
    const res = await patchIncident(id, {status});
    setIncidents(prev => prev.map(i => i.id === id ? {...i, status: res?.status || status} : i));
  };

  const fmtTime = t => new Date(t).toLocaleString();

  return (
    <div style={{fontFamily:'system-ui,sans-serif',maxWidth:1100,margin:'0 auto',padding:20}}>
      <h1 style={{margin:0,padding:'16px 0',fontSize:22}}>🚨 Incident Triage Dashboard</h1>

      <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center',marginBottom:12}}>
        <span style={{fontSize:13,fontWeight:600,color:'#555'}}>Severity:</span>
        <FilterBtn active={sevFilter===null} onClick={()=>setSevFilter(null)} label="All"/>
        {SEV_ORDER.map(s => (
          <FilterBtn key={s} active={sevFilter===s} onClick={()=>setSevFilter(sevFilter===s?null:s)}
            label={s.charAt(0).toUpperCase()+s.slice(1)}
            style={{backgroundColor:sevFilter===s?SEV_COLORS[s].border:'#eee',color:sevFilter===s?'#fff':SEV_COLORS[s].text}}/>
        ))}
        <span style={{marginLeft:16,fontSize:13,fontWeight:600,color:'#555'}}>Status:</span>
        {['new','investigating','resolved','suppressed'].map(s => (
          <FilterBtn key={s} active={statusFilter===s} onClick={()=>setStatusFilter(statusFilter===s?null:s)}
            label={s.charAt(0).toUpperCase()+s.slice(1)}/>
        ))}
      </div>

      {loading ? <p>Loading…</p> : (
        <table style={{width:'100%',borderCollapse:'collapse',fontSize:14}}>
          <thead>
            <tr style={{textAlign:'left',borderBottom:'2px solid #ccc'}}>
              <th style={thS}>ID</th><th style={thS}>Title</th><th style={thS}>Severity</th>
              <th style={thS}>Status</th><th style={thS}>Service</th><th style={thS}>Time</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(i => {
              const sc = SEV_COLORS[i.severity];
              return (
                <tr key={i.id} onClick={()=>setSelected(i.id)}
                   style={{cursor:'pointer',borderBottom:'1px solid #e0e0e0',background:selected===i.id?'#e8eaf6':'#fff'}}>
                  <td style={tdS}><code>{i.id}</code></td>
                  <td style={tdS}>{i.title}</td>
                  <td style={tdS}><span style={{padding:'2px 8px',borderRadius:4,fontSize:12,fontWeight:600,
                    backgroundColor:sc.bg,color:sc.text,border:`1px solid ${sc.border}`}}>
                    {i.severity.toUpperCase()}</span></td>
                  <td style={tdS}><span style={{padding:'2px 8px',borderRadius:4,fontSize:12,fontWeight:600,
                    color:'#fff',backgroundColor:STATUS_COLORS[i.status]}}>{i.status}</span></td>
                  <td style={tdS}><code>{i.service}</code></td>
                  <td style={{...tdS,whiteSpace:'nowrap'}}>{fmtTime(i.created_at)}</td>
                </tr>
              );
            })}
            {filtered.length===0 && <tr><td colSpan={6} style={{padding:20,textAlign:'center',color:'#999'}}>No incidents match filters</td></tr>}
          </tbody>
        </table>
      )}
      <p style={{fontSize:12,color:'#999',marginTop:8}}>{filtered.length} of {incidents.length} incidents</p>

      {selectedInc && (
        <div style={{position:'fixed',top:0,right:0,bottom:0,width:400,background:'#fff',
          borderLeft:'1px solid #ccc',boxShadow:'-4px 0 20px rgba(0,0,0,.1)',padding:24,overflowY:'auto',zIndex:10}}>
          <button onClick={()=>setSelected(null)} style={{position:'absolute',top:12,right:12,border:'none',
            background:'none',fontSize:20,cursor:'pointer'}}>✕</button>
          <h2 style={{marginTop:0,fontSize:18}}>{selectedInc.id}</h2>
          <h3 style={{marginTop:0,fontSize:15,color:'#444'}}>{selectedInc.title}</h3>
          <div style={{display:'flex',gap:8,marginBottom:16}}>
            <span style={{padding:'3px 10px',borderRadius:4,fontWeight:600,fontSize:12,
              backgroundColor:SEV_COLORS[selectedInc.severity].bg,color:SEV_COLORS[selectedInc.severity].text,
              border:`1px solid ${SEV_COLORS[selectedInc.severity].border}`}}>
              {selectedInc.severity.toUpperCase()}</span>
            <span style={{padding:'3px 10px',borderRadius:4,fontWeight:600,fontSize:12,
              color:'#fff',backgroundColor:STATUS_COLORS[selectedInc.status]}}>{selectedInc.status}</span>
          </div>
          <p style={{fontSize:13,lineHeight:1.5}}>{selectedInc.description}</p>
          <div style={{fontSize:13,color:'#555',lineHeight:2}}>
            <div><strong>Service:</strong> <code>{selectedInc.service}</code></div>
            <div><strong>Alerts correlated:</strong> {selectedInc.alerts_count}</div>
            <div><strong>Assigned:</strong> {selectedInc.assigned_to || '—'}</div>
            <div><strong>Created:</strong> {fmtTime(selectedInc.created_at)}</div>
          </div>
          <div style={{marginTop:20,borderTop:'1px solid #eee',paddingTop:16}}>
            <strong style={{fontSize:13}}>Triage Action</strong>
            <div style={{display:'flex',gap:8,marginTop:8,flexWrap:'wrap'}}>
              {['investigating','resolved','suppressed'].map(s => (
                <button key={s} disabled={selectedInc.status===s}
                  onClick={()=>handleStatus(selectedInc.id,s)}
                  style={{padding:'6px 14px',borderRadius:4,border:`1px solid ${STATUS_COLORS[s]}`,
                    background:selectedInc.status===s?STATUS_COLORS[s]:'#fff',
                    color:selectedInc.status===s?'#fff':STATUS_COLORS[s],
                    fontSize:12,fontWeight:600,cursor:selectedInc.status===s?'default':'pointer',
                    opacity:selectedInc.status===s?.6:1}}>
                  {s.charAt(0).toUpperCase()+s.slice(1)}</button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FilterBtn({active,onClick,label,style}) {
  return <button onClick={onClick} style={{padding:'4px 12px',borderRadius:4,border:`1px solid ${active?'#333':'#ccc'}`,
    fontSize:12,fontWeight:600,cursor:'pointer',background:active?'#333':'#fff',
    color:active?'#fff':'#333',...style}}>{label}</button>;
}

const thS = {padding:'10px 8px',fontSize:13,fontWeight:600,color:'#555'};
const tdS = {padding:'10px 8px'};