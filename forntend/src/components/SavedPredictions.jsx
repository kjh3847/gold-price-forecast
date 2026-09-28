import { BookmarkCheck } from 'lucide-react';
import { money, dateLabel } from '../utils/format.js';
export default function SavedPredictions({ rows }) {
  return <section className="panel"><div className="panel-heading"><div><h2>저장한 예측 결과</h2><p>이 브라우저의 임시 저장 내역 · SQLite 미연결</p></div><span className="soft-badge">{rows.length}건</span></div>{!rows.length ? <div className="empty-state"><BookmarkCheck size={26} /><strong>아직 저장된 예측이 없습니다.</strong><span>예측 결과 저장 버튼으로 기록을 남겨보세요.</span></div> : <div className="table-scroll" tabIndex={0} role="region" aria-label="저장한 예측 결과"><table><thead><tr><th>예측 날짜</th><th>기준 날짜</th><th>예측 가격</th><th>데이터</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{dateLabel(row.date)}</td><td>{dateLabel(row.asOf)}</td><td className="predicted-price">{money(row.predictedPrice)}</td><td>Mock</td></tr>)}</tbody></table></div>}</section>;
}
