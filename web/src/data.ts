import { GRADES, type Forecast } from "./types";

export interface LoadedForecast {
  data: Forecast;
  isSample: boolean;
}

const base = import.meta.env.BASE_URL;
export const FORECAST_URL = "/api/forecast/full";
export const SAMPLE_URL = `${base}data/forecast.sample.json`;

/** 화면이 깨지지 않을 최소한의 구조 검사. */
export function isForecast(value: unknown): value is Forecast {
  const v = value as Forecast;
  return (
    !!v &&
    typeof v.as_of === "string" &&
    typeof v.price === "number" &&
    typeof v.sigma_daily === "number" &&
    GRADES.includes(v.grade) &&
    !!v.band &&
    typeof v.band.low === "number" &&
    typeof v.band.high === "number" &&
    Array.isArray(v.history) &&
    !!v.split_rule &&
    GRADES.every((g) => Array.isArray(v.split_rule[g]))
  );
}

async function fetchForecast(url: string, fetcher: typeof fetch): Promise<Forecast> {
  const res = await fetcher(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  const json: unknown = await res.json();
  if (!isForecast(json)) throw new Error(`${url}: 형식이 올바르지 않습니다`);
  return json;
}

/** forecast.json을 읽고, 실패하면 forecast.sample.json으로 대체한다. */
export async function loadForecast(fetcher: typeof fetch = fetch): Promise<LoadedForecast> {
  try {
    return { data: await fetchForecast(FORECAST_URL, fetcher), isSample: false };
  } catch (err) {
    console.warn("forecast.json을 읽지 못해 샘플 데이터를 씁니다", err);
    return { data: await fetchForecast(SAMPLE_URL, fetcher), isSample: true };
  }
}
