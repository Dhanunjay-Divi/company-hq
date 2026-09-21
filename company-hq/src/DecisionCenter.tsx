import React, { useMemo, useState } from 'react';
import { CheckCircle2, GitBranch, Scale, Search, ShieldCheck, SlidersHorizontal } from 'lucide-react';

type AnyRecord = Record<string, any>;

interface Props {
  data: AnyRecord | null;
  loading?: boolean;
  error?: string;
}

function fmt(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unknown';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return String(value);
}

function statusFor(repo: AnyRecord): string {
  if (repo.installed) return 'Integrated';
  const review = String(repo.reviewStatus || '').toLowerCase();
  if (review.includes('readme')) return 'Doc reviewed';
  if (review.includes('metadata')) return 'Inventoried';
  return 'Candidate';
}

function statusClass(label: string): string {
  return label.toLowerCase().replaceAll(' ', '-');
}

export default function DecisionCenter({ data, loading, error }: Props) {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const repositories = data?.repositories || [];
  const categories = useMemo(() => ['all', ...Array.from(new Set(repositories.map((repo: AnyRecord) => repo.category).filter(Boolean))).sort()], [repositories]);
  const filtered = repositories.filter((repo: AnyRecord) => {
    const haystack = `${repo.repo} ${repo.category} ${repo.description} ${repo.reviewStatus} ${repo.nextAction}`.toLowerCase();
    return (category === 'all' || repo.category === category) && haystack.includes(query.toLowerCase());
  });
  const statusCounts = repositories.reduce((counts: AnyRecord, repo: AnyRecord) => {
    const status = statusFor(repo);
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {});

  if (loading) return <div className="decision-center"><div className="empty-inline">Loading stack decisions…</div></div>;
  if (error) return <div className="decision-center"><div className="empty-inline">{error}</div></div>;
  if (!data) return <div className="decision-center"><div className="empty-inline">Decision evidence is not available yet.</div></div>;

  return <div className="decision-center">
    <header className="decision-hero">
      <div>
        <span className="eyebrow">WHY THIS STACK</span>
        <h2>Evidence before adoption</h2>
        <p>Company HQ keeps one authority per responsibility. A repository can be inventoried, reviewed, benchmarked, integrated, or active; those states are deliberately different.</p>
      </div>
      <div className="decision-policy">
        <span><ShieldCheck size={16}/> {data.policy || 'smallest capable route'}</span>
        <span><Scale size={16}/> {data.scope}</span>
      </div>
    </header>

    <section className="decision-grid">
      {(data.decisions || []).map((decision: AnyRecord) => <article className="decision-card" key={decision.area}>
        <div className="decision-card-top"><CheckCircle2 size={18}/><span>{decision.area}</span></div>
        <h3>{decision.primary}</h3>
        <p>{decision.why}</p>
        <dl>
          <div><dt>Fallback</dt><dd>{decision.fallback}</dd></div>
          <div><dt>Not chosen</dt><dd>{decision.notChosen}</dd></div>
          <div><dt>Evidence</dt><dd>{decision.evidence}</dd></div>
        </dl>
      </article>)}
    </section>

    <section className="evidence-strip">
      <article><span>Top-40 catalog</span><strong>{repositories.length}</strong><small>Every listed candidate is accounted for</small></article>
      <article><span>Earlier shared repos</span><strong>{(data.additionalComponents || []).length}</strong><small>Separated from the Notion list</small></article>
      <article><span>Model tokens</span><strong>{fmt(data.actualModelTokens)}</strong><small>Byte savings are not billed savings</small></article>
    </section>

    <section className="comparison-panel">
      <div className="view-heading">
        <div><span className="eyebrow">MEASURED CHALLENGERS</span><h2>What won, and what did not</h2><p>Benchmarks are narrow smoke tests. They guide defaults; they do not replace source verification.</p></div>
      </div>
      <div className="comparison-grid">
        {(data.codeIntelligence || []).map((item: AnyRecord) => <article key={item.name}>
          <h3>{item.name.replaceAll('_', ' ')}</h3>
          <b>{item.status}</b>
          <p>{fmt(item.matched_queries)} / {fmt(item.queries_run)} required queries matched</p>
          <small>{fmt(item.stdout_bytes_median)} median bytes · {fmt(item.query_seconds_median)}s median query</small>
        </article>)}
      </div>
      <div className="comparison-grid">
        {(data.outputReduction || []).map((item: AnyRecord) => <article key={item.case}>
          <h3>{item.case.replaceAll('_', ' ')}</h3>
          <b>{item.rtk_gate_passed ? 'RTK gate passed' : 'Raw fallback'}</b>
          <p>{fmt(item.raw_bytes)} raw bytes → {fmt(item.rtk_bytes)} RTK bytes</p>
          <small>Headroom: {item.headroom_transform || 'not tested here'}</small>
        </article>)}
      </div>
    </section>

    <section className="repo-inventory">
      <div className="view-heading">
        <div><span className="eyebrow">REPOSITORY INVENTORY</span><h2>What we reused, held, or rejected</h2><p>Unknown licenses or metadata-only entries stay as candidates until a file-level review and acceptance test justify adoption.</p></div>
        <label className="search decision-search"><Search size={15}/><input aria-label="Search repository decisions" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search repos…"/></label>
      </div>
      <div className="decision-filters">
        <SlidersHorizontal size={15}/>
        {categories.map((name: string) => <button key={name} className={category === name ? 'active' : ''} onClick={() => setCategory(name)}>{name === 'all' ? 'All' : name}</button>)}
      </div>
      <div className="status-row">
        {Object.entries(statusCounts).map(([name, count]) => <span key={name} className={`status-chip ${statusClass(name)}`}>{name}: {String(count)}</span>)}
      </div>
      <div className="repo-grid">
        {filtered.map((repo: AnyRecord) => {
          const status = statusFor(repo);
          return <article className="repo-card" key={repo.repo}>
            <header><span className={`status-chip ${statusClass(status)}`}>{status}</span><small>{repo.category}</small></header>
            <h3>{repo.repo}</h3>
            <p>{repo.description}</p>
            <dl>
              <div><dt>License</dt><dd>{repo.license}</dd></div>
              <div><dt>Next</dt><dd>{repo.nextAction}</dd></div>
            </dl>
            {repo.url && <a href={repo.url} target="_blank" rel="noreferrer"><GitBranch size={13}/> Source</a>}
          </article>;
        })}
      </div>
    </section>

    <section className="additional-components">
      <div className="view-heading"><div><span className="eyebrow">EARLIER SHARED REPOS</span><h2>Reference, integrated, or default-off</h2><p>These are tracked separately from the top-40 catalog so none of the original sources disappear.</p></div></div>
      <div className="repo-grid compact">
        {(data.additionalComponents || []).map((item: AnyRecord) => <article className="repo-card" key={item.name}>
          <header><span className="status-chip candidate">{item.area}</span></header>
          <h3>{item.name}</h3>
          <p>{item.decision}</p>
          <dl>
            <div><dt>Evidence</dt><dd>{item.evidence}</dd></div>
            <div><dt>Boundary</dt><dd>{item.boundary}</dd></div>
          </dl>
        </article>)}
      </div>
    </section>

    <section className="limitations-panel">
      <h3>Limits that stay visible</h3>
      <ul>{(data.limitations || []).map((item: string) => <li key={item}>{item}</li>)}</ul>
    </section>
  </div>;
}
