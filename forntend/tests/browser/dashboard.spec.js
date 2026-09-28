import { test, expect } from '@playwright/test';

test('desktop: charts, navigation, forecasts, saved records and date filters', async ({ page }) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('response', (response) => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
  page.on('console', (message) => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '시장의 흐름, 데이터로 한눈에.' })).toBeVisible();
  await expect(page.locator('.recharts-area')).toBeVisible();
  await expect(page.getByRole('img', { name: /90개 일별/ })).toBeVisible();
  for (const [period, count] of [['1M', 30], ['6M', 180], ['1Y', 365], ['3M', 90]]) {
    await page.getByRole('button', { name: period, exact: true }).click();
    await expect(page.getByRole('img', { name: new RegExp(`${count}개 일별`) })).toBeVisible();
  }
  await page.getByRole('checkbox', { name: '예측값 비교', exact: true }).uncheck();
  await expect(page.locator('.recharts-line')).toHaveCount(0);
  await page.getByRole('checkbox', { name: '예측값 비교', exact: true }).check();
  await expect(page.locator('.recharts-line')).toHaveCount(1);
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.screenshot({ path: 'test-results/dashboard-desktop.png', fullPage: true });
  await page.getByRole('button', { name: '가격 예측', exact: true }).click();
  await page.getByLabel('예측 날짜', { exact: true }).selectOption('2026-10-05');
  await page.getByRole('button', { name: '예측 결과 저장', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('이 브라우저에 예측 결과를 저장했습니다.');
  await page.getByRole('button', { name: '예측 결과 저장', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('이미 저장한 예측 결과입니다.');
  await page.reload();
  await expect(page.getByRole('region', { name: '저장한 예측 결과' }).getByText('2026.10.05')).toBeVisible();
  await page.getByRole('button', { name: '모델 성능', exact: true }).click();
  await expect(page.getByText('모델 학습 후 표시 예정', { exact: false })).toBeVisible();
  await expect(page.locator('.recharts-line')).toHaveCount(1);
  await page.getByRole('button', { name: '데이터 조회', exact: true }).click();
  await page.getByLabel('시작일').fill('2026-09-01');
  await page.getByLabel('종료일').fill('2026-09-03');
  await expect(page.locator('.table-panel tbody tr')).toHaveCount(3);
  await page.getByLabel('종료일').fill('2026-08-01');
  await expect(page.getByRole('alert')).toContainText('종료일은 시작일보다');
  await page.getByRole('button', { name: '초기화' }).click();
  await page.getByRole('button', { name: '다음 페이지' }).click();
  await expect(page.locator('.pagination')).toContainText('2 / 25');
  await page.getByLabel('시작일').fill('2030-01-01');
  await expect(page.getByText('선택한 기간의 데이터가 없습니다.')).toBeVisible();
  await page.getByRole('button', { name: '금 시세', exact: true }).click();
  await expect(page.getByRole('heading', { name: '금 시세 분석', exact: true })).toBeVisible();
  await expect(page.locator('.recharts-area')).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile: all screens render without page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.locator('.recharts-area')).toBeVisible();
  await page.screenshot({ path: 'test-results/dashboard-mobile.png', fullPage: true });
  for (const name of ['대시보드', '금 시세', '가격 예측', '모델 성능', '데이터 조회']) {
    await page.getByRole('button', { name, exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.getByRole('button', { name: '대시보드', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('storage failures appear as feedback without breaking the dashboard', async ({ page }) => {
  await page.addInitScript(() => { localStorage.setItem('gold-forecast.saved.v1', '{bad'); });
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('저장 내역을 읽을 수 없습니다');
  await expect(page.locator('.recharts-area')).toBeVisible();
  await page.getByRole('button', { name: '예측 결과 저장', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('저장 내역을 읽을 수 없습니다');
});
