import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { downloadOnePagerPdf, getOnePager } from "../api/client";

export default function OnePagerPage() {
  const { id = "" } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["one-pager", id],
    queryFn: () => getOnePager(id),
  });

  if (isLoading) return <div className="p-10">Loading one-pager…</div>;
  if (isError || !data) return <div className="p-10">One-pager not found. <Link to="/">Return home</Link></div>;

  const copy = () => navigator.clipboard.writeText(
    `${data.title}\n\n${data.executive_summary}\n\n${data.challenge}\n\n${data.solution}`,
  );

  return <main className="max-w-5xl mx-auto p-8">
    <Link className="text-indigo-600" to="/">← Back to workspace</Link>
    <div className="flex gap-2 justify-end">
      <button className="btn primary" onClick={() => downloadOnePagerPdf(data.one_pager_id)}>Download PDF</button>
      <button className="btn border" disabled>Download Markdown</button>
      <button className="btn border" onClick={copy}>Copy</button>
      <button className="btn border" disabled>Regenerate</button>
    </div>
    <article className="card p-10 mt-5">
      <div className="text-sm text-indigo-600">PROJECT INTELLIGENCE HUB · {data.generated_date}</div>
      <h1 className="text-4xl font-bold mt-3">{data.title}</h1>
      <p className="text-lg text-slate-500 mt-2">{data.case_study_line}</p>
      <Section title="Executive Summary" value={data.executive_summary} />
      <Section title="The Challenge" value={data.challenge} />
      <Section title="Our Solution" value={data.solution} />
      <List title="Key Features" values={data.key_features} />
      <List title="Quantified Outcomes" values={data.quantified_outcomes} />
      <Section title="Business Value" value={data.business_value} />
      <List title="Known Gaps / Caveats" values={data.known_gaps} />
      <h2 className="text-xl font-bold mt-7">Sources Used</h2>
      {data.sources_used.map(source => <div className="mt-2 text-sm" key={source.document_id}>{source.file_name} <span className="text-slate-400">({source.document_id})</span></div>)}
    </article>
  </main>;
}

function Section({ title, value }: { title: string; value: string }) {
  return <section className="mt-7"><h2 className="text-xl font-bold">{title}</h2><p className="mt-2 leading-7">{value}</p></section>;
}

function List({ title, values }: { title: string; values: string[] }) {
  return <section className="mt-7"><h2 className="text-xl font-bold">{title}</h2><ul className="list-disc ml-6 mt-2">{values.map(value => <li key={value}>{value}</li>)}</ul></section>;
}
