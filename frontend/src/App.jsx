import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Bot, Zap, Database, ShieldCheck, Clock3, Sparkles, Plus, AlertTriangle, Github, LoaderCircle } from 'lucide-react';

const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const newId = () => `s-${crypto.randomUUID()}`;

function Metadata({ data }) {
  return <div className="meta">
    <span data-testid="meta-source" className={'tag '+(data.resolution_source === 'LLM_CACHE' ? 'cached' : 'live')}>{data.resolution_source}</span>
    <span data-testid="meta-model" className="tag">{data.model}</span>
    <span data-testid="meta-latency" className="tag"><Clock3 size={12}/> {data.latency_ms} ms</span>
    <span data-testid="meta-input-tokens" className="tag">In: {data.input_tokens}</span>
    <span data-testid="meta-output-tokens" className="tag">Out: {data.output_tokens}</span>
    {data.fallback_attempts > 0 && <span className="tag fallback">Failover: {data.fallback_attempts}</span>}
  </div>;
}

export default function App() {
  const [session, setSession] = useState(newId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('Checking API');
  const bottom = useRef(null);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);
  useEffect(() => { fetch(`${API}/health`).then(r => {if (!r.ok) throw Error(); return r.json();}).then(() => setStatus('API online')).catch(() => setStatus('API unavailable')); }, []);
  const reset = () => { if (busy) return; setSession(newId()); setMessages([]); setInput(''); };
  const send = async (preset) => {
    const text = (preset ?? input).trim();
    if (!text || busy || text.length > 4000) return;
    setInput(''); setBusy(true);
    setMessages(old => [...old, { role: 'user', content: text }]);
    try {
      const response = await fetch(`${API}/chat`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({session_id: session, message: text, ...(systemPrompt.trim() ? {system_prompt: systemPrompt.trim()} : {})}) });
      const data = await response.json();
      if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
      setMessages(old => [...old, {role:'assistant', content:data.reply, metadata:data.metadata}]);
    } catch (error) {
      setMessages(old => [...old, {role:'error', content: error.message || 'Something went wrong. Please try again.'}]);
    } finally { setBusy(false); }
  };
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon"><Sparkles size={21}/></div><div><strong>Lyftr AI</strong><small>Resilient Intelligence</small></div></div>
      <button className="new-chat" onClick={reset}><Plus size={18}/> New conversation</button>
      <div className="sidebar-label">CURRENT SESSION</div>
      <div className="session-box" title={session}>{session.slice(0, 19)}...</div>
      <div className="sidebar-bottom"><div className="feature"><ShieldCheck size={17}/> Automatic key failover</div><div className="feature"><Database size={17}/> Intelligent response cache</div><div className="feature"><Zap size={17}/> Request-level analytics</div><div className="status"><span className={status==='API online'?'dot':'dot offline'}/>{status}</div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><strong>AI Assistant</strong><span className="top-sub">Powered by LiteLLM</span></div><div className="header-pill"><span className="dot"/> Resilient Chat</div></header>
      <div className="conversation">
        {messages.length===0 && <div className="welcome"><div className="hero-icon"><Bot size={30}/></div><h1>How can I help you today?</h1><p>Ask anything. Every answer includes transparent model analytics, with smart caching and automatic failover behind the scenes.</p><div className="suggestions">{['Explain how API caching works','What is a FastAPI backend?','How does LLM failover work?'].map(q => <button key={q} onClick={() => send(q)}>{q}<ArrowUp size={14}/></button>)}</div></div>}
        <div className="message-list">{messages.map((m, i) => <div className={'message '+m.role} key={i} {...(m.role==='assistant'?{'data-testid':'assistant-message'}:{})}>
          {m.role!=='user' && <div className={'avatar '+(m.role==='error'?'error-avatar':'')} >{m.role==='error'?<AlertTriangle size={16}/>:<Bot size={17}/>}</div>}
          <div className="message-body"><div className="bubble">{m.content}</div>{m.metadata && <Metadata data={m.metadata}/>}</div>
        </div>)}{busy && <div className="message assistant"><div className="avatar"><Bot size={17}/></div><div className="thinking"><LoaderCircle size={17} className="spin"/> Thinking...</div></div>}<div ref={bottom}/></div>
      </div>
      <div className="composer-wrap"><div className="composer"><textarea data-testid="chat-input" value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}} placeholder="Message Lyftr AI..." maxLength={4000} rows={2} disabled={busy}/><button data-testid="send-button" aria-label="Send message" onClick={()=>send()} disabled={!input.trim()||busy}><ArrowUp size={20}/></button></div><details className="system-prompt"><summary>Customize system prompt (optional)</summary><textarea data-testid="system-prompt-input" value={systemPrompt} onChange={e=>setSystemPrompt(e.target.value)} placeholder="You are a helpful assistant..." rows={2}/></details><div className="footnote">Built with React, FastAPI, LiteLLM & SQLite · Shift+Enter for a new line</div></div>
    </main>
  </div>;
}
