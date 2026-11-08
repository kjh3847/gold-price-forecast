# 로컬 컨테이너 검증 결과

## EC2 첫 배포 확인 (2026-11-09 KST)

서울 리전의 Ubuntu 24.04 x86 EC2에서 `sudo bash deploy/deploy.sh`로 첫 배포를 실행했습니다.
Docker Engine 29.1.3 및 Compose 2.40.3 환경에서 Python 테스트 76개가 통과하고,
웹 테스트와 빌드를 포함한 이미지 빌드가 완료됐습니다. 배포 로그에서 다음 결과를 확인했습니다.

```text
Container gold-forecast-api-1  Healthy
Container gold-forecast-web-1  Healthy
Deployment OK: release=run-20261108150631 forecast-request=2026-09-24
```

배포 스크립트의 예측 API 확인 결과는 기준일 `2026-09-24`, 등급 `LOW`,
5거래일 가격 범위 약 `4050.27 ~ 4509.67 USD/oz`였습니다.
웹의 8080 포트를 검증자 IP에만 허용하고 해당 컴퓨터에서 예측 페이지가 표시되는 것을 확인했습니다.
EC2에서 입력 저장·재조회와 S3·CloudWatch 실제 전송은 별도 확인 항목입니다.

## EC2 재배포 확인 (2026-11-09 KST)

화면 제목을 ‘이번 주 변동성 전망’으로 변경한 `7e18db0`을 `git pull --ff-only`로 받은 뒤,
기존 8080 바인딩을 유지하도록 `WEB_BIND=0.0.0.0`을 지정해 `deploy/deploy.sh`를 다시 실행했습니다.
Python 테스트 76개가 통과했고 웹 테스트와 빌드도 완료됐습니다. 아래는 EC2 로그에서 확인한 결과입니다.

```text
Updating 5908b65..7e18db0
Container gold-forecast-api-1  Healthy
Container gold-forecast-web-1  Healthy
Deployment OK: release=run-20261108151935 forecast-request=2026-09-24
```

예측 API가 기존 기준일과 가격 범위를 반환했습니다. 이 로그는 서버 재배포 결과이며,
브라우저에서 새 제목을 확인하는 절차는 별도로 진행합니다.

## 로컬 검증 (2026-11-02 KST)

- 검증일: 2026-11-02 (KST)
- 실행 환경: Windows Docker Desktop / Linux containers
- Docker 29.0.1, Compose v2.40.3-desktop.1
- 실행: `./deploy/deploy.ps1 -Release container-check-20261102`
- AWS 배포/전송은 제외, Docker Hub 로그인 없이 공개 기반 이미지 다운로드 성공

## 실제 통과한 항목

1. Python 테스트용 이미지 빌드 및 컨테이너 내 전체 pytest: **65 passed**.
2. 웹 빌드 단계의 Vitest: **53 passed**, TypeScript 검사와 Vite 빌드 성공.
3. API/웹 런타임 이미지 빌드 성공.
4. Docker 볼륨의 SQLite에 가격 2,692행 로딩, 520거래일 모델 예측 저장.
5. 2026-09-24: sigma=0.013111394731087946, grade=LOW,
   band_low=4050.2684566766275, band_high=4509.668096170422.
6. Nginx 웹 페이지와 `/api/health`, `/api/forecast/full`, `/api/forecast/latest` 정상 응답.
7. 웹 프록시를 통해 입력 123456원/기타 저장, 접수번호 조회, T/F와 숫자 정답 저장 성공.
8. 동일 볼륨을 유지한 채 `compose up --force-recreate`로 API와 웹 컨테이너 재생성 성공.
9. 재생성 후 입력값, 예측 스냅샷, 정답, 정답 등록 시각의 완전 일치 확인.
10. API와 웹 컨테이너 모두 **healthy**. 외부 바인딩은 `127.0.0.1:8080`만 사용.

검증용 접수번호: `37f85283-f8b5-4f94-8554-592679b2be4a`.
T/F 값 False와 가격 4300 USD/oz는 기능 시험용 합성 입력이며 실제 시장 정답이 아닙니다.
AWS 결과는 s3=disabled, cloudwatch=disabled로 확인했습니다.

## 제한 및 경고

- 기존 웹 의존성의 npm audit 6건은 유지됩니다. 테스트 실패는 아니며 별도 의존성 검토가 필요합니다.
- Python 테스트에서 Starlette/httpx 사용 중단 예정 경고 1건이 있었으며 테스트는 모두 통과했습니다.
- Linux Bash 배포 스크립트는 문법·모의 명령 흐름을 확인했습니다. 실제 배포는 Windows PowerShell에서 수행했습니다.
- 예측은 제공 CSV 마지막 날짜 기준이며 실시간 시세가 아닙니다.
- 호스트 개발 DB와 Docker 볼륨 DB는 서로 독립적입니다.
- 컨테이너는 사용자가 확인할 수 있도록 실행 상태로 두었습니다. `docker compose stop`으로 정지할 수 있습니다.
