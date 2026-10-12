import { formatDate, formatDateTimeKst } from "../format";

interface Props {
  asOf: string;
  generatedAt: string;
  isSample: boolean;
}

export function Header({ asOf, generatedAt, isSample }: Props) {
  return (
    <header className="header">
      <div className="header__brand">
        <span className="header__logo" aria-hidden="true">
          🪙
        </span>
        <h1>금 분할매수 도우미</h1>
      </div>
      <dl className="header__meta">
        <div>
          <dt>기준일</dt>
          <dd>{formatDate(asOf)}</dd>
        </div>
        <div>
          <dt>마지막 업데이트</dt>
          <dd>{formatDateTimeKst(generatedAt)}</dd>
        </div>
      </dl>
      {isSample && (
        <p className="badge badge--sample" role="status">
          샘플 데이터 — 최신 forecast.json을 불러오지 못해 예시 데이터를 보여주고 있어요
        </p>
      )}
    </header>
  );
}
