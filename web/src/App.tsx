import { useEffect, useState } from "react";
import { BandCard } from "./components/BandCard";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { PlanCalculator } from "./components/PlanCalculator";
import { ScoreCard } from "./components/ScoreCard";
import { WeatherCard } from "./components/WeatherCard";
import { loadForecast, type LoadedForecast } from "./data";

type State = { status: "loading" } | { status: "error"; message: string } | ({ status: "ready" } & LoadedForecast);

export default function App() {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    loadForecast()
      .then((loaded) => !cancelled && setState({ status: "ready", ...loaded }))
      .catch((err: unknown) => !cancelled && setState({ status: "error", message: String(err) }));
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return <p className="page-status">데이터를 불러오는 중…</p>;
  }
  if (state.status === "error") {
    return (
      <p className="page-status" role="alert">
        데이터를 불러오지 못했어요. ({state.message})
      </p>
    );
  }

  const { data, isSample } = state;
  return (
    <div className="page">
      <Header asOf={data.as_of} generatedAt={data.generated_at} isSample={isSample} />
      <main className="main">
        <WeatherCard data={data} />
        <BandCard data={data} />
        <PlanCalculator grade={data.grade} splitRule={data.split_rule} />
        <ScoreCard evaluation={data.evaluation} />
      </main>
      <Footer />
    </div>
  );
}
