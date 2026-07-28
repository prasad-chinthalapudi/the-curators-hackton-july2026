import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createColumnHelper, flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type RowSelectionState } from "@tanstack/react-table";
import { CheckCircle2, FileText, Folder, Home, Lightbulb, MessageSquarePlus, PanelsTopLeft, Search, Sparkles, X, XCircle, AlertTriangle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { checkReadiness, downloadOnePagerPdf, generateOnePager, saveKnowledge, searchDocuments } from "../api/client";
import type { Coverage, Document, Filters, Readiness, Status } from "../types";

const suggestions = ["Healthcare Data Warehouse", "Snowflake Migration", "Azure Data Engineering", "Customer 360", "GenAI Projects"];
const filterGroups = [
  ["Document Type", "file_types", ["pptx", "pdf", "docx"]],
  ["Technology", "technologies", ["Azure", "Snowflake", "Databricks", "ADF", "AWS", "Power BI", "Python", "Machine Learning", "GenAI"]],
  ["Industry", "industries", ["Healthcare", "Retail", "Travel", "Insurance", "Banking", "Hospitality"]],
] as const;

export default function Workspace() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("Need Healthcare projects using Snowflake and Azure Databricks");
  const [submitted, setSubmitted] = useState(query);
  const [filters, setFilters] = useState<Filters>({ file_types: [], technologies: [], industries: [] });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<RowSelectionState>({});
  const [within, setWithin] = useState("");
  const [preview, setPreview] = useState<Document | null>(null);
  const [ready, setReady] = useState<Readiness | null>(null);
  const [knowledge, setKnowledge] = useState(false);
  const [chat, setChat] = useState(false);
  const [toast, setToast] = useState("");

  const search = useQuery({
    queryKey: ["search", submitted, filters, page],
    queryFn: () => searchDocuments({ query: submitted, filters, page, page_size: 10, sort_by: "relevance" }),
  });
  const readiness = useMutation({ mutationFn: checkReadiness, onSuccess: setReady });
  const generate = useMutation({
    mutationFn: async (documentIds: string[]) => {
      const result = await generateOnePager(documentIds);
      await downloadOnePagerPdf(result.one_pager_id);
      return result;
    },
    onSuccess: result => navigate(`/one-pagers/${result.one_pager_id}`),
  });
  const docs = useMemo(() => search.data?.documents.filter(doc => doc.file_name.toLowerCase().includes(within.toLowerCase())) ?? [], [search.data, within]);
  const ids = Object.keys(selected).filter(key => selected[key]);

  const toggle = (key: "file_types" | "technologies" | "industries", value: string) => {
    setPage(1);
    setFilters(current => ({ ...current, [key]: current[key].includes(value) ? current[key].filter(item => item !== value) : [...current[key], value] }));
  };
  const placeholder = (label: string) => {
    setToast(`${label} is coming soon`);
    window.setTimeout(() => setToast(""), 2000);
  };

  const columns = useMemo(() => {
    const column = createColumnHelper<Document>();
    return [
      column.display({ id: "select", header: ({ table }) => <input aria-label="Select all" type="checkbox" checked={table.getIsAllPageRowsSelected()} onChange={table.getToggleAllPageRowsSelectedHandler()} />, cell: ({ row }) => <input aria-label={`Select ${row.original.file_name}`} type="checkbox" checked={row.getIsSelected()} onChange={row.getToggleSelectedHandler()} /> }),
      column.accessor("file_name", { header: "Document Name", cell: info => <button className="font-semibold text-indigo-700 text-left" onClick={() => setPreview(info.row.original)}>{info.getValue()}</button> }),
      column.accessor("file_type", { header: "Type", cell: info => <span className="badge uppercase">{info.getValue()}</span> }),
      column.accessor("tags", { header: "Tags / Extracted Info", cell: info => <div className="flex flex-wrap gap-1">{info.getValue().map(tag => <span className="badge" key={tag}>{tag}</span>)}</div> }),
      column.accessor("match_score", { header: "Match Score", cell: info => <div className="w-20"><div className="text-xs">{Math.round(info.getValue() * 100)}%</div><div className="h-1.5 bg-slate-200 rounded"><div className="h-1.5 bg-emerald-500 rounded" style={{ width: `${info.getValue() * 100}%` }} /></div></div> }),
      column.accessor("summary", { header: "AI Summary", cell: info => <span className="text-sm">{info.getValue()}</span> }),
      column.accessor("added_on", { header: "Added On" }),
    ];
  }, []);
  const table = useReactTable({ data: docs, columns, state: { rowSelection: selected }, enableRowSelection: true, onRowSelectionChange: setSelected, getRowId: row => row.document_id, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });

  return <div className="min-h-screen">
    <Header />
    <div className="flex items-start">
      <IconNav />
      <Filters filters={filters} toggle={toggle} clear={() => setFilters({ file_types: [], technologies: [], industries: [] })} setFilters={setFilters} />
      <main className="flex-1 min-w-0 p-5">
        <h2 className="text-xl font-bold">What are you looking for?</h2>
        <form className="flex mt-4" onSubmit={event => { event.preventDefault(); setPage(1); setSubmitted(query); }}>
          <input value={query} onChange={event => setQuery(event.target.value)} className="flex-1 border rounded-l-lg p-3" />
          <button className="primary px-7 rounded-r-lg flex items-center gap-2"><Search size={18} /> Search</button>
        </form>
        <div className="flex gap-2 mt-3 flex-wrap"><span className="text-xs text-slate-500 py-1">Example searches:</span>{suggestions.map(item => <button key={item} className="badge" onClick={() => { setQuery(item); setSubmitted(item); }}>{item}</button>)}</div>

        {search.isLoading && <div className="animate-pulse mt-6 h-44 card" />}
        {search.isError && <div className="card p-6 mt-6 text-red-600">Unable to load results. Confirm the FastAPI server is running.</div>}
        {search.data && <>
          <section className="card p-5 mt-6">
            <h3 className="font-bold flex items-center gap-2"><Sparkles className="text-indigo-600" size={19} /> AI Understanding</h3>
            <div className="grid grid-cols-4 gap-3 mt-4">
              {[["Documents Found", search.data.understanding.documents_found], ["Related Clusters", search.data.understanding.related_clusters], ["Key Technologies", search.data.understanding.key_technologies_count], ["Overall Confidence", `${Math.round(search.data.understanding.confidence * 100)}%`]].map(([label, value]) => <div className="border rounded-lg p-4" key={label}><div className="text-2xl font-bold">{value}</div><div className="text-xs text-slate-500">{label}</div></div>)}
            </div>
            <p className="text-sm text-slate-600 mt-4">{search.data.understanding.summary}</p>
            <div className="flex gap-2 mt-4 items-center"><b className="text-xs">Common Technologies:</b>{search.data.understanding.common_technologies.map(item => <span className="badge" key={item}>{item}</span>)}<button className="ml-auto btn border text-indigo-600" onClick={() => placeholder("Cluster overview")}>View Cluster Overview</button></div>
          </section>

          <section className="card mt-5 overflow-hidden">
            <div className="p-4 flex items-center gap-3"><div><h3 className="font-bold">Matching Documents <span className="text-slate-400">({search.data.total_documents})</span></h3><p className="text-xs text-slate-500">Select documents and generate a one pager or chat with AI</p></div><div className="ml-auto relative"><Search className="absolute left-3 top-2.5 text-slate-400" size={16} /><input className="border rounded p-2 pl-9" placeholder="Search in results" value={within} onChange={event => setWithin(event.target.value)} /></div><button className="btn border">Columns</button><button className="btn border">Sort by: Relevance</button></div>
            {docs.length === 0 ? <div className="p-10 text-center">No matching documents. Try a broader search.</div> : <div className="overflow-x-auto"><table className="w-full text-left"><thead className="bg-slate-100">{table.getHeaderGroups().map(group => <tr key={group.id}>{group.headers.map(header => <th className="p-3 text-xs whitespace-nowrap" key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map(row => <tr className="border-t" key={row.id}>{row.getVisibleCells().map(cell => <td className="p-3" key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}</tbody></table></div>}
            <div className="p-3 flex justify-end gap-3 text-sm"><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {search.data.total_pages}</span><button disabled={page >= search.data.total_pages} onClick={() => setPage(value => value + 1)}>Next</button></div>
            <div className="border-t bg-white p-4 flex gap-2 items-center">
              <b className="text-indigo-700 mr-auto">{ids.length} document{ids.length === 1 ? "" : "s"} selected</b>
              <button disabled={!ids.length} className="btn border disabled:opacity-40" onClick={() => setChat(true)}>Chat with Selected</button>
              <button disabled={!ids.length} className="btn primary disabled:opacity-40" onClick={() => readiness.mutate(ids)}>Generate One Pager</button>
              {["Executive Summary", "Compare Docs", "More"].map(item => <button disabled={!ids.length} className="btn border disabled:opacity-40" onClick={() => placeholder(item)} key={item}>{item}</button>)}
            </div>
          </section>
        </>}
      </main>
      <Assistant coverage={docs[0]?.coverage} technologies={search.data?.understanding.common_technologies ?? []} total={search.data?.total_documents ?? 0} summary={search.data?.understanding.summary ?? ""} onKnowledge={() => setKnowledge(true)} onChat={() => setChat(true)} />
    </div>

    {preview && <div className="fixed inset-0 bg-black/30 flex justify-end z-30" onClick={() => setPreview(null)}><aside className="w-[480px] bg-white h-full p-7" onClick={event => event.stopPropagation()}><button className="float-right" onClick={() => setPreview(null)}><X /></button><span className="badge uppercase">{preview.file_type}</span><h2 className="text-2xl font-bold mt-4">{preview.file_name}</h2><p className="mt-4">{preview.summary}</p><h3 className="font-bold mt-6">Technologies</h3><div className="flex gap-2 mt-2">{preview.technologies.map(item => <span className="badge" key={item}>{item}</span>)}</div><p className="mt-6">{preview.industry} · {preview.year}</p></aside></div>}
    {ready && <Modal title="One-Pager Readiness" close={() => setReady(null)}><p>{ready.selected_document_count} documents selected · <b>{ready.status.replaceAll("_", " ")}</b></p><p className="text-sm text-slate-500 mt-2">Generate creates and downloads a PDF, then opens the one-pager preview.</p><CoverageView coverage={ready.coverage} />{ready.gaps.map(gap => <div key={gap.field} className="mt-2 text-sm">{gap.message}</div>)}{generate.isError && <p className="text-sm text-red-600 mt-4">PDF generation failed. Confirm the API is running and try again.</p>}<div className="flex justify-end gap-2 mt-6"><button className="btn" onClick={() => setReady(null)}>Cancel</button><button disabled={generate.isPending} className="btn primary disabled:opacity-50" onClick={() => generate.mutate(ids)}>{generate.isPending ? "Generating PDF…" : "Generate PDF"}</button></div></Modal>}
    {knowledge && <KnowledgeModal ids={ids} close={() => setKnowledge(false)} success={() => { setKnowledge(false); setToast("Knowledge saved"); }} />}
    {chat && <ChatModal count={ids.length || search.data?.total_documents || 0} close={() => setChat(false)} />}
    {toast && <div className="fixed bottom-5 right-5 bg-slate-900 text-white p-4 rounded-lg z-50">{toast}</div>}
  </div>;
}

function Header() { return <header className="h-16 bg-white border-b flex items-center px-4 gap-4"><div className="bg-blue-800 text-white rounded-lg p-2 font-black">PIH</div><div><h1 className="font-bold">Project Intelligence Hub</h1><p className="text-xs text-slate-500">AI-Powered Project Knowledge Assistant</p></div><nav className="ml-auto flex items-center gap-6 text-sm"><span>My Workspaces</span><span>History</span><span>Help</span><span className="rounded-full bg-blue-700 text-white p-2">SK</span></nav></header>; }
function IconNav() { return <aside className="w-16 min-h-[calc(100vh-4rem)] sticky top-0 bg-white border-r flex flex-col items-center gap-9 pt-7">{[Home, Folder, FileText, PanelsTopLeft, Lightbulb].map((Icon, index) => <Icon key={index} className={index === 0 ? "text-blue-600" : "text-slate-400"} size={21} />)}</aside>; }
function Filters({ filters, toggle, clear, setFilters }: { filters: Filters; toggle: (key: "file_types" | "technologies" | "industries", value: string) => void; clear: () => void; setFilters: React.Dispatch<React.SetStateAction<Filters>> }) {
  return <aside className="w-60 shrink-0 p-5 border-r bg-white min-h-[calc(100vh-4rem)]"><h2 className="font-bold text-lg border-b pb-4">Filters</h2>{filterGroups.map(([title, key, items]) => <div className="py-4 border-b" key={title}><h3 className="font-semibold text-sm mb-2">{title}</h3>{items.map(item => <label className="block text-sm py-1.5" key={item}><input className="mr-2 accent-blue-600" type="checkbox" checked={filters[key].includes(item)} onChange={() => toggle(key, item)} />{item}</label>)}</div>)}<div className="py-4"><h3 className="font-semibold text-sm">Year</h3><div className="flex gap-2 mt-2"><input className="w-24 border rounded p-2" placeholder="From" type="number" onChange={event => setFilters(value => ({ ...value, year_from: event.target.value ? Number(event.target.value) : undefined }))} /><input className="w-24 border rounded p-2" placeholder="To" type="number" onChange={event => setFilters(value => ({ ...value, year_to: event.target.value ? Number(event.target.value) : undefined }))} /></div></div><button className="btn border w-full" onClick={clear}>Clear All Filters</button></aside>;
}
function Assistant({ coverage, technologies, total, summary, onKnowledge, onChat }: { coverage?: Coverage; technologies: string[]; total: number; summary: string; onKnowledge: () => void; onChat: () => void }) {
  return <aside className="w-72 shrink-0 border-l bg-white p-4 sticky top-0 h-[calc(100vh-4rem)] overflow-y-auto">
    <div className="flex items-center"><h2 className="font-bold flex items-center gap-2"><Sparkles size={18} className="text-blue-600" /> AI Assistant</h2><button className="ml-auto btn border text-xs text-blue-700 flex gap-1" onClick={onChat}><MessageSquarePlus size={14} /> New Chat</button></div>
    <section className="card p-4 mt-4 text-sm"><p>I found <b>{total}</b> relevant documents for your query.</p><p className="mt-3">{summary || "Run a search to see project insights."}</p><p className="mt-3">You can:</p><ul className="list-disc ml-5 mt-2 space-y-1"><li>Generate a one pager</li><li>Chat with these documents</li><li>Compare documents</li><li>View cluster overview</li></ul></section>
    <section className="card p-4 mt-4"><h3 className="font-semibold text-sm">Top Technologies</h3>{technologies.slice(0, 4).map((item, index) => <div key={item} className="mt-3 text-xs"><div className="flex justify-between"><span>{item}</span><span>{87 - index * 11}%</span></div><div className="h-1.5 bg-slate-200 rounded mt-1"><div className="h-1.5 bg-blue-600 rounded" style={{ width: `${87 - index * 11}%` }} /></div></div>)}</section>
    <section className="card p-4 mt-4"><div className="flex justify-between"><h3 className="font-semibold text-sm">Knowledge Coverage</h3><button className="text-xs text-blue-600" onClick={onKnowledge}>Add</button></div>{coverage ? <CoverageView coverage={coverage} compact /> : <p className="text-xs text-slate-500 mt-3">Coverage appears with results.</p>}</section>
    <section className="card p-4 mt-4"><h3 className="text-xs text-slate-500">Ask a follow-up</h3>{["Show me similar projects", "What are the key outcomes?", "Which clients are mentioned?"].map(item => <button className="block btn border text-xs text-blue-700 mt-2 w-full text-left" onClick={onChat} key={item}>{item}</button>)}</section>
  </aside>;
}
function StatusIcon({ status }: { status: Status }) { return status === "available" ? <CheckCircle2 size={15} className="text-green-600" /> : status === "partial" ? <AlertTriangle size={15} className="text-amber-500" /> : <XCircle size={15} className="text-red-500" />; }
function CoverageView({ coverage, compact = false }: { coverage: Coverage; compact?: boolean }) { return <div className={compact ? "mt-3 space-y-2" : "grid grid-cols-2 gap-2 mt-4"}>{Object.entries(coverage).map(([key, value]) => <div className="flex justify-between items-center text-xs bg-slate-50 p-2 rounded capitalize" key={key}><span>{key.replaceAll("_", " ")}</span><span className="flex items-center gap-1"><StatusIcon status={value} />{value !== "available" && value}</span></div>)}</div>; }
function Modal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) { return <div className="fixed inset-0 bg-black/40 grid place-items-center z-40"><div className="card p-6 w-[620px] max-h-[90vh] overflow-auto"><button className="float-right" onClick={close}><X /></button><h2 className="text-xl font-bold">{title}</h2>{children}</div></div>; }
function ChatModal({ count, close }: { count: number; close: () => void }) { const [message, setMessage] = useState(""); return <Modal title="AI Assistant · New Chat" close={close}><div className="bg-slate-50 rounded-lg p-4 mt-4 text-sm">Ask questions across {count} relevant document{count === 1 ? "" : "s"}. This prototype uses placeholder responses.</div><div className="mt-4 min-h-32 border rounded-lg p-4 text-sm text-slate-500">Try: “What are the common business outcomes?”</div><div className="flex mt-4"><input className="flex-1 border rounded-l-lg p-3" placeholder="Ask a follow-up…" value={message} onChange={event => setMessage(event.target.value)} /><button className="primary px-5 rounded-r-lg" onClick={() => setMessage("")}>Send</button></div></Modal>; }
function KnowledgeModal({ ids, close, success }: { ids: string[]; close: () => void; success: () => void }) {
  const [question, setQuestion] = useState("Who was the delivery lead?");
  const [answer, setAnswer] = useState("");
  const [contributor, setContributor] = useState("Hackathon User");
  const save = useMutation({ mutationFn: () => saveKnowledge({ question, answer, contributor, related_document_ids: ids }), onSuccess: success });
  return <Modal title="Add Missing Knowledge" close={close}><p className="text-sm mt-2">Missing information: delivery team and lessons learned</p>{[["Question", question, setQuestion], ["Answer", answer, setAnswer], ["Contributor", contributor, setContributor]].map(([label, value, setter]) => <label className="block mt-4" key={label as string}>{label as string}<textarea className="block w-full border rounded p-2 mt-1" value={value as string} onChange={event => (setter as (value: string) => void)(event.target.value)} /></label>)}<p className="text-sm mt-3">Related document IDs: {ids.join(", ") || "None selected"}</p><button disabled={!answer || save.isPending} className="btn primary mt-5" onClick={() => save.mutate()}>Save Knowledge</button></Modal>;
}
