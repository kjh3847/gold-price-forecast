import { ArrowUpRight, ArrowDownRight } from 'lucide-react';
export default function StatCard({ label, value, unit, detail, change, icon: Icon, accent = false }) {
  return <article className={`stat-card ${accent ? 'accent' : ''}`}><div className="stat-label">{label}<Icon size={18} /></div><div className="stat-value">{value}<span>{unit}</span></div><div className="stat-detail">{change != null && <span className={change >= 0 ? 'positive' : 'negative'}>{change >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}{change > 0 ? '+' : ''}{change.toFixed(2)}%</span>}{detail}</div></article>;
}
