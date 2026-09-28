import { ChartNoAxesCombined, LayoutDashboard, TrendingUp, Sparkles, Gauge, Database, ArrowUpRight } from 'lucide-react';

export const navigation = [
  { id: 'dashboard', label: '대시보드', icon: LayoutDashboard },
  { id: 'prices', label: '금 시세', icon: TrendingUp },
  { id: 'prediction', label: '가격 예측', icon: Sparkles },
  { id: 'performance', label: '모델 성능', icon: Gauge },
  { id: 'data', label: '데이터 조회', icon: Database },
];
export default function Layout({ page, onNavigate, children }) {
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">본문으로 이동</a>
    <aside className="sidebar">
      <a className="brand" href="#dashboard" onClick={(e) => { e.preventDefault(); onNavigate('dashboard'); }}>
        <span className="brand-mark"><ChartNoAxesCombined size={25} /></span>
        <span>Gold Forecast<small>금 시세 예측 프로그램</small></span>
      </a>
      <div className="nav-caption">WORKSPACE</div>
      <nav aria-label="주요 메뉴">{navigation.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} aria-current={page === id ? 'page' : undefined} onClick={() => onNavigate(id)}><Icon size={19} />{label}{page === id && <span className="nav-dot" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="research-card"><span className="tiny-label">RESEARCH PROJECT</span><strong>데이터로 읽는 금의 흐름</strong><p>과거 시세부터 미래 예측까지,<br />한눈에 살펴보세요.</p><span className="research-icon"><ArrowUpRight size={19} /></span></div><div className="workspace-status"><span className="status-dot" />데모 워크스페이스<span>v0.1</span></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><span>워크스페이스 <span className="breadcrumb-slash">/</span> <strong>{navigation.find((item) => item.id === page)?.label}</strong></span><div className="topbar-right"><span className="demo-badge"><span />MOCK DATA</span><span className="avatar">GF</span></div></header><main id="main-content" tabIndex={-1}>{children}</main><footer><span>Gold Price Forecast <span className="footer-divider">/</span> 머신러닝 팀 프로젝트</span><span>시연용 데이터 · 실제 시세 및 투자 판단용 정보가 아닙니다.</span></footer></div>
  </div>;
}
