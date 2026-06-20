import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Activity,
  CheckCheck,
  Clock,
  Download,
  FileText,
  FileUp,
  Gauge,
  Image as ImageIcon,
  MessageCircle,
  Paperclip,
  RefreshCw,
  Send,
  Settings as SettingsIcon,
  Trash2,
  Upload,
  Users,
  Webhook,
  XCircle
} from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import './styles.css';

const client = new QueryClient();

type Candidate = {
  id: number;
  phone: string;
  name: string;
  current_status: string;
  last_seen_at: string;
};

type Outbound = {
  id: number;
  transaction_id: string;
  to_phone: string;
  sender: string;
  template_id: string;
  status: string;
  created_at: string;
  rendered_preview: string;
  request_payload_json: string;
};

type WebhookEvent = {
  id: number;
  event_type: string;
  webhook_type: string;
  target_url: string;
  response_status: number | null;
  retry_count: number;
  created_at: string;
  payload_json: string;
};

type Inbound = {
  id: number;
  message_type: string;
  text_body: string;
  file_url: string;
  file_name: string;
  mime_type: string;
  webhook_payload_json: string;
  created_at: string;
};

type Uploaded = {
  id: number;
  original_filename: string;
  public_mock_url: string;
  mime_type: string;
  created_at: string;
};

const TOKEN_KEY = 'wa_admin_token';

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken();
  return { ...(extra || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

function handleUnauthorized() {
  clearToken();
  if (window.location.pathname !== '/login') window.location.assign('/login');
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: authHeaders(init?.headers) });
  if (response.status === 401) {
    handleUnauthorized();
    throw new Error('Unauthorized');
  }
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function useApi<T>(path: string) {
  return useQuery({ queryKey: [path], queryFn: () => api<T>(path) });
}

const indiaDateTime = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Asia/Kolkata'
});

const indiaTime = new Intl.DateTimeFormat('en-IN', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  timeZone: 'Asia/Kolkata'
});

function formatIndiaDateTime(value: string) {
  return indiaDateTime.format(new Date(value));
}

function formatIndiaTime(value: string) {
  return indiaTime.format(new Date(value));
}

function Button({ children, onClick, title }: { children: React.ReactNode; onClick?: () => void; title?: string }) {
  return (
    <button type="button" title={title} onClick={onClick} className="inline-flex h-9 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm font-medium text-ink shadow-sm hover:bg-panel">
      {children}
    </button>
  );
}

function Shell() {
  const nav = [
    ['/', Gauge, 'Dashboard'],
    ['/candidates', Users, 'Candidates'],
    ['/messages', MessageCircle, 'Outbound'],
    ['/scenarios', Activity, 'Scenarios'],
    ['/webhooks', Webhook, 'Webhooks'],
    ['/settings', SettingsIcon, 'Settings']
  ] as const;
  return (
    <div className="min-h-screen bg-[#edf2ef] text-ink">
      <div className="border-b border-[#b8c6bd] bg-[#1f342b] text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
          <div>
            <div className="text-sm font-semibold uppercase tracking-wide">Mock WhatsApp Provider</div>
            <div className="text-xs text-[#cfe4d9]">Not connected to real WhatsApp</div>
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-md bg-white/10 px-3 py-1 text-xs">TrustSignal-compatible</div>
            <LlmActions />
            <button
              type="button"
              onClick={() => { clearToken(); window.location.assign('/login'); }}
              className="rounded-md bg-white/10 px-3 py-1 text-xs font-medium hover:bg-white/20"
            >
              Log out
            </button>
          </div>
        </div>
      </div>
      <div className="mx-auto grid max-w-7xl grid-cols-[220px_1fr] gap-6 px-5 py-6">
        <aside className="space-y-2">
          {nav.map(([to, Icon, label]) => (
            <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium ${isActive ? 'bg-white shadow-soft' : 'hover:bg-white/70'}`}>
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </aside>
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/candidates" element={<Candidates />} />
            <Route path="/candidates/:id" element={<CandidateChat />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/scenarios" element={<Scenarios />} />
            <Route path="/webhooks" element={<Webhooks />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function parseError(error: unknown): string {
  const raw = (error as { message?: string })?.message || 'Request failed';
  try {
    const parsed = JSON.parse(raw);
    return parsed?.errors?.[0]?.message || raw;
  } catch {
    return raw;
  }
}

function LlmActions() {
  const [busy, setBusy] = React.useState<'' | 'clear' | 'download'>('');
  const [message, setMessage] = React.useState<{ tone: 'ok' | 'err'; text: string } | null>(null);
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const clearCache = async () => {
    if (!window.confirm('Clear the LLM fixture cache? This deletes all recorded fixtures.')) return;
    setBusy('clear');
    setMessage(null);
    try {
      const data = await api<{ deleted_count?: number }>('/mock/llm/clear-cache', { method: 'POST' });
      setMessage({ tone: 'ok', text: `Cache cleared — ${data.deleted_count ?? 0} fixture(s) deleted.` });
    } catch (error) {
      setMessage({ tone: 'err', text: parseError(error) });
    } finally {
      setBusy('');
    }
  };

  const downloadCache = async () => {
    setBusy('download');
    setMessage(null);
    try {
      const data = await api<{ count?: number }>('/mock/llm/export-cache');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'fixtures.json';
      link.click();
      URL.revokeObjectURL(url);
      setMessage({ tone: 'ok', text: `Downloaded ${data.count ?? 0} fixture(s) as fixtures.json.` });
    } catch (error) {
      setMessage({ tone: 'err', text: parseError(error) });
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-2 rounded-md bg-white/10 px-3 py-1 text-xs font-medium hover:bg-white/20"
      >
        <Webhook size={14} />LLM Action
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-60 rounded-lg border border-line bg-white p-3 text-ink shadow-soft">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">LLM Actions</h2>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={clearCache}
              disabled={busy !== ''}
              className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-red-600 px-3 text-sm font-medium text-white shadow-sm hover:bg-red-700 disabled:opacity-60"
            >
              <Trash2 size={15} />{busy === 'clear' ? 'Clearing…' : 'Clear Cache'}
            </button>
            <button
              type="button"
              onClick={downloadCache}
              disabled={busy !== ''}
              className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-mint px-3 text-sm font-medium text-white shadow-sm hover:opacity-90 disabled:opacity-60"
            >
              <Download size={15} />{busy === 'download' ? 'Downloading…' : 'Download Cache'}
            </button>
          </div>
          {message && (
            <div className={`mt-2 rounded-md px-3 py-2 text-xs font-medium ${message.tone === 'ok' ? 'bg-emerald-50 text-mint' : 'bg-red-50 text-coral'}`}>
              {message.text}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: React.ComponentType<{ size?: number; className?: string }> }) {
  return (
    <div className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">{label}</div>
        <Icon size={18} className="text-mint" />
      </div>
      <div className="mt-3 text-3xl font-semibold">{value}</div>
    </div>
  );
}

function Dashboard() {
  const { data, refetch } = useApi<any>('/mock/dashboard');
  if (!data) return <PageTitle title="Dashboard" />;
  const chart = [
    { name: 'Sent', value: data.outbound_messages },
    { name: 'Inbound', value: data.inbound_messages },
    { name: 'CVs', value: data.cvs_received },
    { name: 'Failures', value: data.failures }
  ];
  return (
    <section className="space-y-5">
      <PageHeader title="Dashboard" onRefresh={() => refetch()} />
      <div className="grid grid-cols-4 gap-4">
        <Metric label="Candidates" value={data.total_candidates} icon={Users} />
        <Metric label="Outbound" value={data.outbound_messages} icon={MessageCircle} />
        <Metric label="Inbound" value={data.inbound_messages} icon={Activity} />
        <Metric label="CVs Received" value={data.cvs_received} icon={FileUp} />
        <Metric label="Delivered" value={data.delivered} icon={CheckCheck} />
        <Metric label="Read" value={data.read} icon={Clock} />
        <Metric label="Failures" value={data.failures} icon={XCircle} />
        <Metric label="Webhook Retries" value={data.webhook_retries} icon={RefreshCw} />
      </div>
      <div className="grid grid-cols-[1.2fr_.8fr] gap-4">
        <Panel title="Message Mix">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" fill="#2f8c67" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
        <Panel title="Recent Activity">
          <div className="space-y-2">
            {data.recent_activity.map((item: any, index: number) => (
              <div key={index} className="rounded-md border border-line bg-panel px-3 py-2 text-sm">
                <div className="font-medium">{item.phone}</div>
                <div className="text-slate-600">{item.kind} · {item.status}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function PageTitle({ title }: { title: string }) {
  return <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>;
}

function PageHeader({ title, onRefresh }: { title: string; onRefresh?: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <PageTitle title={title} />
      {onRefresh && <Button onClick={onRefresh}><RefreshCw size={15} />Refresh</Button>}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <h2 className="mb-3 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Candidates() {
  const { data, refetch } = useApi<Candidate[]>('/mock/candidates');
  const [selected, setSelected] = React.useState<number[]>([]);
  const candidates = data || [];
  const allIds = candidates.map((candidate) => candidate.id);
  const allSelected = allIds.length > 0 && selected.length === allIds.length;

  const toggle = (id: number) =>
    setSelected((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  const toggleAll = () => setSelected(allSelected ? [] : allIds);

  const action = async (candidate: Candidate, text: string) => {
    await api(`/mock/candidates/${candidate.id}/reply`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text }) });
    refetch();
  };
  const deleteSelected = async () => {
    if (!selected.length) return;
    if (!window.confirm(`Delete ${selected.length} candidate(s)? This also removes their messages, uploads, and webhook events.`)) return;
    await api('/mock/candidates/bulk-delete', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids: selected })
    });
    setSelected([]);
    refetch();
  };

  const selectAllBox = (
    <input type="checkbox" aria-label="Select all candidates" checked={allSelected} onChange={toggleAll} className="h-4 w-4 cursor-pointer accent-mint" />
  );

  return (
    <section className="space-y-4">
      <PageHeader title="Candidates" onRefresh={() => refetch()} />
      {selected.length > 0 && (
        <div className="flex items-center justify-between rounded-md border border-line bg-white px-4 py-2 shadow-soft">
          <span className="text-sm text-slate-600">{selected.length} selected</span>
          <button
            type="button"
            onClick={deleteSelected}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-red-600 px-3 text-sm font-medium text-white shadow-sm hover:bg-red-700"
          >
            <Trash2 size={15} />Delete {selected.length}
          </button>
        </div>
      )}
      <Table headers={[selectAllBox, 'Phone', 'Name', 'Current Status', 'Last Activity', 'CV Received', 'Actions']}>
        {candidates.map((candidate) => (
          <tr key={candidate.id} className={selected.includes(candidate.id) ? 'bg-emerald-50/60' : undefined}>
            <td>
              <input
                type="checkbox"
                aria-label={`Select ${candidate.phone}`}
                checked={selected.includes(candidate.id)}
                onChange={() => toggle(candidate.id)}
                className="h-4 w-4 cursor-pointer accent-mint"
              />
            </td>
            <td><Link className="font-medium text-mint" to={`/candidates/${candidate.id}`}>{candidate.phone}</Link></td>
            <td>{candidate.name}</td>
            <td><Badge value={candidate.current_status} /></td>
            <td>{formatIndiaDateTime(candidate.last_seen_at)}</td>
            <td>{candidate.current_status.includes('cv') ? 'Yes' : 'No'}</td>
            <td className="space-x-2">
              <Button onClick={() => action(candidate, 'YES')} title="Reply YES"><MessageCircle size={15} />Reply</Button>
              <Button onClick={() => action(candidate, 'CALL_ME')} title="Reply CALL_ME"><Activity size={15} />Call</Button>
            </td>
          </tr>
        ))}
      </Table>
    </section>
  );
}

function CandidateChat() {
  const { id } = useParams();
  const { data, refetch } = useApi<any>(`/mock/candidates/${id}`);
  const [draft, setDraft] = React.useState('');
  const [isUploading, setIsUploading] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  if (!data) return <PageTitle title="Candidate" />;

  const postReply = (text: string) =>
    api(`/mock/candidates/${id}/reply`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text })
    }).then(() => refetch());
  const sendDraft = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft('');
    await postReply(text);
  };
  const uploadMock = async (name: string, type: string, bytes: string, invalid = false) => {
    const form = new FormData();
    form.append('file', new File([bytes], name, { type }));
    await fetch(`/mock/candidates/${id}/upload-cv?invalid=${invalid}`, { method: 'POST', body: form, headers: authHeaders() });
    refetch();
  };
  const uploadLocalFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append('file', file);
        await fetch(`/mock/candidates/${id}/upload-cv`, { method: 'POST', body: form, headers: authHeaders() });
      }
      await refetch();
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };
  const setStatus = async (message: Outbound, status: string) => {
    await api(`/mock/messages/${message.transaction_id}/status`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ status })
    });
    refetch();
  };

  const outbound: Outbound[] = data.outbound || [];
  const inbound: Inbound[] = data.inbound || [];
  const files: Uploaded[] = data.files || [];
  const events: WebhookEvent[] = data.webhook_events || [];
  const chatItems = [
    ...outbound.map((item) => ({
      id: `out-${item.id}`,
      kind: 'ats' as const,
      at: item.created_at,
      text: item.rendered_preview || item.template_id || 'WhatsApp template',
      status: item.status,
      payload: item.request_payload_json
    })),
    ...inbound.map((item) => ({
      id: `in-${item.id}`,
      kind: 'candidate' as const,
      at: item.created_at,
      text: item.text_body || item.file_name || item.message_type,
      fileUrl: item.file_url,
      fileName: item.file_name,
      mimeType: item.mime_type,
      messageType: item.message_type,
      payload: item.webhook_payload_json
    })),
    ...events.map((item) => ({
      id: `event-${item.id}`,
      kind: 'event' as const,
      at: item.created_at,
      text: `${item.webhook_type} / ${item.event_type}`,
      status: item.response_status ? String(item.response_status) : item.retry_count > 0 ? `retry ${item.retry_count}` : 'stored',
      payload: item.payload_json
    }))
  ].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));

  return (
    <section className="space-y-4">
      <PageHeader title={`${data.candidate.name} - ${data.candidate.phone}`} onRefresh={() => refetch()} />
      <div className="grid grid-cols-[1fr_310px] gap-4">
        <section className="overflow-hidden rounded-lg border border-line bg-white shadow-soft">
          <div className="flex items-center justify-between border-b border-line bg-[#1f342b] px-4 py-3 text-white">
            <div>
              <div className="font-semibold">{data.candidate.name}</div>
              <div className="text-xs text-[#cfe4d9]">{data.candidate.phone} - {data.candidate.current_status}</div>
            </div>
            <div className="rounded-md bg-white/10 px-2 py-1 text-xs">ATS chat simulator</div>
          </div>
          <div className="chat-surface">
            {chatItems.map((item) => (
              <ChatBubble key={item.id} item={item} />
            ))}
          </div>
          <div className="border-t border-line bg-[#f6f8f7] p-3">
            <div className="mb-2 flex flex-wrap gap-2">
              {['YES', 'NO', 'RESCHEDULE', 'CALL_ME', 'STOP'].map((text) => (
                <Button key={text} onClick={() => postReply(text)}><MessageCircle size={15} />{text}</Button>
              ))}
            </div>
            <div className="flex items-end gap-2">
              <input ref={fileInputRef} type="file" multiple className="hidden" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" onChange={(event) => uploadLocalFiles(event.currentTarget.files)} />
              <Button onClick={() => fileInputRef.current?.click()} title="Upload local files">
                <Paperclip size={16} />{isUploading ? 'Uploading' : 'Attach'}
              </Button>
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    sendDraft();
                  }
                }}
                placeholder="Type a candidate reply"
                className="min-h-10 flex-1 resize-none rounded-md border border-line bg-white px-3 py-2 text-sm outline-none focus:border-mint focus:ring-4 focus:ring-emerald-100"
              />
              <button type="button" onClick={sendDraft} className="inline-flex h-10 items-center gap-2 rounded-md bg-mint px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#287a59]">
                <Send size={16} />Send
              </button>
            </div>
          </div>
        </section>
        <aside className="space-y-4">
          <Panel title="Message Status">
            <div className="space-y-2">
              {outbound.slice(0, 5).map((message) => (
                <div key={message.id} className="rounded-md border border-line bg-panel p-3">
                  <div className="truncate text-xs font-semibold">{message.transaction_id}</div>
                  <div className="mt-1"><Badge value={message.status} /></div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {['delivered', 'read', 'failed'].map((status) => (
                      <Button key={status} onClick={() => setStatus(message, status)}><CheckCheck size={15} />{status}</Button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Local Uploads">
            <div className="space-y-2">
              <Button onClick={() => fileInputRef.current?.click()}><Paperclip size={15} />Choose local files</Button>
              <Button onClick={() => uploadMock('resume.pdf', 'application/pdf', '%PDF-1.4')}><Upload size={15} />Mock PDF CV</Button>
              <Button onClick={() => uploadMock('resume.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'docx')}><Upload size={15} />Mock DOCX CV</Button>
              <Button onClick={() => uploadMock('broken.bin', 'application/octet-stream', '', true)}><XCircle size={15} />Invalid File</Button>
            </div>
            <div className="mt-4 space-y-2">
              {files.map((file) => (
                <a key={file.id} href={file.public_mock_url} target="_blank" className="flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-mint">
                  <FileText size={15} />{file.original_filename}
                </a>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </section>
  );
}

function ChatBubble({ item }: { item: any }) {
  if (item.kind === 'event') {
    return (
      <div className="my-3 flex justify-center">
        <div className="flex items-center gap-2 rounded-md bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 shadow-sm">
          <span>{item.text} - {item.status} - {formatIndiaTime(item.at)}</span>
          {item.payload && <PayloadButton label="Full payload" payload={item.payload} />}
        </div>
      </div>
    );
  }
  const isAts = item.kind === 'ats';
  const isImage = String(item.mimeType || '').startsWith('image/');
  return (
    <div className={`flex ${isAts ? 'justify-start' : 'justify-end'}`}>
      <div className={`chat-bubble ${isAts ? 'chat-bubble-ats' : 'chat-bubble-candidate'}`}>
        <div className="mb-1 text-[11px] font-semibold uppercase text-slate-500">{isAts ? 'ATS' : 'Candidate'}</div>
        {item.fileUrl && isImage ? (
          <a href={item.fileUrl} target="_blank">
            <img src={item.fileUrl} alt={item.fileName || 'upload'} className="mb-2 max-h-44 rounded-md object-cover" />
          </a>
        ) : item.fileUrl ? (
          <a href={item.fileUrl} target="_blank" className="mb-2 flex items-center gap-2 rounded-md bg-white/70 px-3 py-2 text-sm font-semibold text-mint">
            {item.messageType === 'image' ? <ImageIcon size={16} /> : <FileText size={16} />}
            {item.fileName || 'Uploaded file'}
          </a>
        ) : null}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{item.text}</div>
        <div className="mt-2 flex items-center justify-end gap-2 text-[11px] text-slate-500">
          {item.payload && <PayloadButton label={isAts ? 'Request payload' : 'Received payload'} payload={item.payload} />}
          <span>{formatIndiaTime(item.at)}</span>
          {item.status && <span>{item.status}</span>}
        </div>
      </div>
    </div>
  );
}

function CandidateDetail() {
  const { id } = useParams();
  const { data, refetch } = useApi<any>(`/mock/candidates/${id}`);
  if (!data) return <PageTitle title="Candidate" />;
  const postReply = (text: string) => api(`/mock/candidates/${id}/reply`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text }) }).then(() => refetch());
  const upload = async (name: string, type: string, bytes: string, invalid = false) => {
    const form = new FormData();
    form.append('file', new File([bytes], name, { type }));
    await fetch(`/mock/candidates/${id}/upload-cv?invalid=${invalid}`, { method: 'POST', body: form, headers: authHeaders() });
    refetch();
  };
  return (
    <section className="space-y-4">
      <PageTitle title={`${data.candidate.name} · ${data.candidate.phone}`} />
      <Panel title="Quick Actions">
        <div className="flex flex-wrap gap-2">
          {['YES', 'NO', 'RESCHEDULE', 'CALL_ME', 'Random text'].map((text) => <Button key={text} onClick={() => postReply(text)}><MessageCircle size={15} />{text}</Button>)}
          <Button onClick={() => upload('resume.pdf', 'application/pdf', '%PDF-1.4')}><Upload size={15} />PDF CV</Button>
          <Button onClick={() => upload('resume.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'docx')}><Upload size={15} />DOCX CV</Button>
          <Button onClick={() => upload('broken.bin', 'application/octet-stream', '', true)}><XCircle size={15} />Invalid File</Button>
          <Button onClick={() => postReply('Sent an image')}><FileUp size={15} />Send Image</Button>
        </div>
      </Panel>
      <Panel title="Timeline">
        {[...data.outbound.map((x: any) => ({ kind: 'Outbound', text: x.rendered_preview, at: x.created_at })), ...data.inbound.map((x: any) => ({ kind: 'Inbound', text: x.text_body || x.file_name, at: x.created_at })), ...data.webhook_events.map((x: any) => ({ kind: 'Webhook', text: `${x.webhook_type}/${x.event_type}`, at: x.created_at }))].sort((a: any, b: any) => Date.parse(b.at) - Date.parse(a.at)).map((item: any, index: number) => (
          <div key={index} className="border-b border-line py-3 last:border-b-0">
            <div className="text-sm font-semibold">{item.kind}</div>
            <div className="text-sm text-slate-700">{item.text}</div>
            <div className="text-xs text-slate-500">{formatIndiaDateTime(item.at)}</div>
          </div>
        ))}
      </Panel>
    </section>
  );
}

function Messages() {
  const { data, refetch } = useApi<Outbound[]>('/mock/messages');
  const setStatus = async (m: Outbound, status: string) => {
    await api(`/mock/messages/${m.transaction_id}/status`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ status }) });
    refetch();
  };
  return (
    <section className="space-y-4">
      <PageHeader title="Outbound Messages" onRefresh={() => refetch()} />
      <Table headers={['Transaction ID', 'To', 'Sender', 'Template', 'Status', 'Created At', 'Actions']}>
        {(data || []).map((m) => (
          <tr key={m.id}>
            <td className="max-w-[210px] truncate">{m.transaction_id}</td>
            <td>{m.to_phone}</td>
            <td>{m.sender}</td>
            <td>{m.template_id || 'agent'}</td>
            <td><Badge value={m.status} /></td>
            <td>{formatIndiaDateTime(m.created_at)}</td>
            <td className="space-x-2">
              <PayloadButton label="Payload" payload={m.request_payload_json} />
              {['delivered', 'read', 'failed'].map((s) => <Button key={s} onClick={() => setStatus(m, s)}><CheckCheck size={15} />{s}</Button>)}
            </td>
          </tr>
        ))}
      </Table>
    </section>
  );
}

function Webhooks() {
  const { data, refetch } = useApi<WebhookEvent[]>('/mock/webhook-events');
  const retry = async (id: number) => {
    await api(`/mock/webhook-events/${id}/retry`, { method: 'POST' });
    refetch();
  };
  return (
    <section className="space-y-4">
      <PageHeader title="Webhook Logs" onRefresh={() => refetch()} />
      <Table headers={['Event Type', 'Webhook Type', 'Target URL', 'Response Status', 'Retry Count', 'Created At', 'Actions']}>
        {(data || []).map((event) => (
          <tr key={event.id}>
            <td>{event.event_type}</td>
            <td>{event.webhook_type}</td>
            <td className="max-w-[260px] truncate">{event.target_url || 'stored locally'}</td>
            <td>{event.response_status || '-'}</td>
            <td>{event.retry_count}</td>
            <td>{formatIndiaDateTime(event.created_at)}</td>
            <td className="space-x-2">
              <PayloadButton label="Payload" payload={event.payload_json} />
              <Button onClick={() => retry(event.id)}><RefreshCw size={15} />Retry</Button>
            </td>
          </tr>
        ))}
      </Table>
    </section>
  );
}

function Scenarios() {
  const { data, refetch } = useApi<any[]>('/mock/scenarios');
  const create = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api('/mock/scenarios', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(Object.fromEntries(form))
    });
    event.currentTarget.reset();
    refetch();
  };
  return (
    <section className="space-y-4">
      <PageHeader title="Scenario Builder" onRefresh={() => refetch()} />
      <Panel title="Add Scenario">
        <form onSubmit={create} className="grid grid-cols-5 gap-3">
          <input name="phone" required placeholder="9100000003" className="field" />
          <input name="name" required placeholder="Delivered + YES" className="field" />
          <input name="behavior" required placeholder="yes" className="field" />
          <input name="auto_status_flow" placeholder="delivered+read" className="field" />
          <button className="rounded-md bg-mint px-3 font-medium text-white">Save</button>
        </form>
      </Panel>
      <Table headers={['Phone', 'Name', 'Behavior', 'Status Flow', 'Enabled']}>
        {(data || []).map((s) => <tr key={s.id}><td>{s.phone}</td><td>{s.name}</td><td>{s.behavior}</td><td>{s.auto_status_flow}</td><td>{s.enabled ? 'Yes' : 'No'}</td></tr>)}
      </Table>
    </section>
  );
}

function Settings() {
  const { data, refetch } = useApi<any>('/mock/settings');
  const [test, setTest] = React.useState<any>(null);
  const save = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const patch = Object.fromEntries(new FormData(event.currentTarget));
    await api('/mock/settings', { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(patch) });
    refetch();
  };
  const testConnection = async () => setTest(await api('/mock/settings/test-ats-connection', { method: 'POST' }));
  if (!data) return <PageTitle title="Settings" />;
  return (
    <section className="space-y-4">
      <PageHeader title="Settings" onRefresh={() => refetch()} />
      <Panel title="Runtime Configuration">
        <form onSubmit={save} className="grid grid-cols-2 gap-3">
          {['ats_webhook_url', 'valid_senders', 'default_sender', 'public_base_url', 'ats_webhook_retry_count', 'ats_webhook_retry_interval_ms', 'ats_webhook_timeout_ms'].map((key) => (
            <label key={key} className="text-sm font-medium">
              {key}
              <input name={key} defaultValue={data[key]} className="field mt-1 w-full" />
            </label>
          ))}
          <label className="text-sm font-medium">
            valid_api_keys
            <input name="valid_api_keys" defaultValue={data.valid_api_keys} className="field mt-1 w-full" />
          </label>
          <div className="col-span-2 flex gap-2">
            <button className="rounded-md bg-mint px-4 py-2 font-medium text-white">Save Settings</button>
            <Button onClick={testConnection}><Webhook size={15} />Test ATS Connection</Button>
          </div>
        </form>
        {test && <pre className="mt-4 max-h-52 overflow-auto rounded-md bg-[#17211c] p-3 text-xs text-white">{JSON.stringify(test, null, 2)}</pre>}
      </Panel>
    </section>
  );
}

function Table({ headers, children }: { headers: React.ReactNode[]; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-white shadow-soft">
      <table className="w-full text-left text-sm">
        <thead className="bg-panel text-xs uppercase text-slate-600">
          <tr>{headers.map((h, i) => <th key={i} className="px-4 py-3 font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const tone = value.includes('fail') || value.includes('invalid') ? 'bg-red-50 text-coral' : value.includes('read') || value.includes('delivered') ? 'bg-emerald-50 text-mint' : 'bg-amber-50 text-amber';
  return <span className={`rounded-md px-2 py-1 text-xs font-semibold ${tone}`}>{value}</span>;
}

function PayloadButton({ label, payload }: { label: string; payload: string }) {
  const [open, setOpen] = React.useState(false);
  const pretty = React.useMemo(() => {
    try {
      return JSON.stringify(JSON.parse(payload), null, 2);
    } catch {
      return payload || '{}';
    }
  }, [payload]);
  return (
    <>
      <Button onClick={() => setOpen(true)}><FileText size={15} />{label}</Button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-5">
          <div className="w-full max-w-4xl rounded-lg border border-line bg-white shadow-soft">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="font-semibold">Received Payload</div>
              <Button onClick={() => setOpen(false)}>Close</Button>
            </div>
            <pre className="max-h-[70vh] overflow-auto bg-[#17211c] p-4 text-xs leading-relaxed text-white">{pretty}</pre>
          </div>
        </div>
      )}
    </>
  );
}

function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      if (!response.ok) {
        setError('Invalid username or password');
        return;
      }
      const data = await response.json();
      setToken(data.token);
      navigate('/');
    } catch {
      setError('Could not reach the server');
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#edf2ef] px-5 text-ink">
      <div className="w-full max-w-sm rounded-lg border border-line bg-white p-6 shadow-soft">
        <div className="mb-1 text-sm font-semibold uppercase tracking-wide text-[#1f342b]">Mock WhatsApp Provider</div>
        <div className="mb-5 text-xs text-slate-500">Admin sign in</div>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm font-medium">
            Username
            <input autoFocus value={username} onChange={(e) => setUsername(e.target.value)} className="field mt-1 w-full" />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="field mt-1 w-full" />
          </label>
          {error && <div className="rounded-md bg-red-50 px-3 py-2 text-xs font-medium text-coral">{error}</div>}
          <button disabled={busy} className="w-full rounded-md bg-mint px-4 py-2 font-medium text-white disabled:opacity-60">
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}

function Root() {
  const location = useLocation();
  const token = getToken();
  if (location.pathname === '/login') {
    return token ? <Navigate to="/" replace /> : <Login />;
  }
  if (!token) return <Navigate to="/login" replace />;
  return <Shell />;
}

function App() {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Root />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
