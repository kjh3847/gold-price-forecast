export function Footer() {
  return (
    <footer className="footer">
      <p>
        이 서비스는 금값이 오를지 내릴지 예측하지 않으며, 투자 권유가 아닙니다. 예상 변동성에 따라 매수 시점을 나누는
        일정 안내일 뿐 수익을 보장하지 않습니다.
      </p>
      <p>분할매수가 한 번에 사는 것보다 평균 매수 단가를 높일 수도 있습니다. 투자 판단과 책임은 본인에게 있습니다.</p>
      <p className="footer__small">강의 프로젝트 · 데이터: 달러 금값(USD/oz) 일간 종가</p>
    </footer>
  );
}
