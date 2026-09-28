import { useEffect, useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { getPrices } from '../services/goldService.js';
import { money, dateLabel } from '../utils/format.js';

export default function PriceTable({ compact = false, onNavigate }) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const invalid = Boolean(start && end && start > end);
  useEffect(() => {
    let active = true;
    setPage(1);
    setError('');
    if (invalid) { setRows([]); setLoading(false); return; }
    setLoading(true);
    getPrices({ period: '1Y', start, end }).then((data) => { if (active) setRows([...data].reverse()); }).catch(() => { if (active) { setRows([]); setError('가격 데이터를 불러오지 못했습니다.'); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [start, end, invalid]);
  const pageSize = compact ? 5 : 15;
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const visible = rows.slice((page - 1) * pageSize, page * pageSize);
  return <section className="panel table-panel"><div className="panel-heading"><div><h2>{compact ? '최근 금 시세' : '과거 금 시세 조회'}</h2><p>일별 시세와 예측 가격을 확인하세요. <span className="unit-inline">KRW / g · mock</span></p></div>{compact && <button className="text-button" onClick={onNavigate}>전체 데이터 보기<ChevronRight size={15} /></button>}</div>
    {!compact && <div className="table-filters"><CalendarDays size={18} /><label>시작일<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label><span>—</span><label>종료일<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label><button className="secondary-button" onClick={() => { setStart(''); setEnd(''); }}>초기화</button><span className="result-count">{rows.length}건</span></div>}
    {invalid && <p role="alert" className="inline-error">종료일은 시작일보다 빠를 수 없습니다.</p>}{error && <p role="alert" className="inline-error">{error}</p>}
    <div className="table-scroll" tabIndex={0} role="region" aria-label="금 시세 데이터 테이블"><table><thead><tr><th scope="col">날짜</th>{['시가', '고가', '저가', '종가', '예측가'].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{!loading && visible.map((row) => <tr key={row.date}><td>{dateLabel(row.date)}</td><td>{money(row.open)}</td><td>{money(row.high)}</td><td>{money(row.low)}</td><td className="close-price">{money(row.close)}</td><td className="predicted-price">{money(row.predicted)}</td></tr>)}</tbody></table>{loading ? <div className="empty-state">데이터를 불러오는 중입니다…</div> : !visible.length && <div className="empty-state"><Search size={23} />선택한 기간의 데이터가 없습니다.</div>}</div>
    <div className="table-footer"><span>{compact ? `최근 ${visible.length}개 관측값` : `${rows.length}건 중 ${rows.length ? (page - 1) * pageSize + 1 : 0}–${Math.min(page * pageSize, rows.length)}건`}<span className="table-source"> · 시연용 데이터</span></span>{!compact ? <div className="pagination"><button aria-label="이전 페이지" disabled={page === 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button><span>{page} / {pageCount}</span><button aria-label="다음 페이지" disabled={page >= pageCount} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button></div> : <span className="table-source">매일의 움직임을 한눈에</span>}</div>
  </section>;
}
