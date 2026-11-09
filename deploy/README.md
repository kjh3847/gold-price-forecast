# Windows / Linux 배포 스크립트

교수님 예제의 **테스트 → 빌드 → 실행 → 정상 동작 확인** 흐름을 금 예측 서비스에 적용했습니다.
예제의 `deploy.yml`은 GitHub Actions가 실행하는 워크플로 설정이며 Windows/Linux에서
직접 실행하는 스크립트가 아닙니다. 이 폴더의 스크립트는 Docker가 설치된 **현재 컴퓨터**에서
웹/API를 컨테이너로 실행합니다. Linux EC2에 프로젝트를 가져와 실행하면 그 EC2에 배포됩니다.
PC에서 실행한다고 AWS에 자동 업로드되지는 않습니다.

## 준비

- Docker Engine + Docker Compose v2 (`up --wait` 지원)
- Windows: Docker Desktop을 시작하고 Linux containers 모드 사용, PowerShell
- Linux: 실행 계정에 Docker 사용 권한 필요, Bash
- 처음에는 이미지와 Python/npm 패키지 다운로드를 위한 인터넷 연결 필요
- 기본 호스트 포트 8080. 기존 개발 서버 5173/8000과 별개

## Windows (프로젝트 루트 PowerShell)

```powershell
.\deploy\deploy.ps1 -CheckOnly
.\deploy\deploy.ps1
# 데이터 파일을 갱신했다면 유효한 거래일을 지정
.\deploy\deploy.ps1 -ForecastDate '2026-09-24' -Release 'class-demo-1'
```

실행 정책으로 차단되면 조직 정책을 확인하거나 아래 Linux 스크립트를 사용하세요.
스크립트는 시스템 실행 정책이나 보안 설정을 변경하지 않습니다.

## Linux (프로젝트 루트)

```bash
bash deploy/deploy.sh 2026-09-24 --check-only
bash deploy/deploy.sh
RELEASE=class-demo-1 bash deploy/deploy.sh 2026-09-24
```

기본 날짜 2026-09-24는 제공 CSV의 마지막 날짜입니다. 오늘 날짜의 실시간 예측이 아닙니다.
새 데이터를 준비하지 않은 채 이후 거래일을 주면 배치가 실패하고 배포를 중단합니다.
기존 DB에 더 최근 예측이 있으면 최신 예측 API는 그 더 최근 예측을 반환합니다.

## 확인 / 종료 / 재배포

브라우저에서 http://localhost:8080 을 열고 예측 기준일·범위, 입력 저장과 접수번호 조회를 확인하세요.

```bash
docker compose ps
docker compose logs --tail=100
docker compose stop
```

문구 변경 후 같은 배포 스크립트를 다시 실행하면 테스트와 빌드를 거쳐 다시 배포합니다.
SQLite는 `gold-forecast_gold-data` 이름의 Docker 볼륨에 보관됩니다.
컨테이너 교체/stop/down으로 입력 기록을 삭제하지 않습니다. `down -v`는 볼륨을 삭제하므로 사용하지 마세요.
기존 호스트 `gold_service.db`는 복사/수정하지 않으며 Docker용 DB는 별도입니다.
이 스크립트는 무중단 배포나 자동 롤백을 제공하지 않습니다. 모델 배치는 기존 볼륨을 갱신하므로
중요한 기록은 배포 전에 백업하세요. 테스트·빌드 실패 시 서비스 교체 단계로 진행하지 않습니다.

## AWS에서 사용할 때 (실제 설정/배포는 사용자 진행)

기본은 `127.0.0.1:8080`으로 이 컴퓨터에서만 접속됩니다. EC2 외부 공개가 필요하면
적절한 보안 그룹·HTTPS 구성을 준비한 뒤 환경변수를 설정하세요.

```bash
export WEB_BIND=0.0.0.0
export WEB_PORT=8080
bash deploy/deploy.sh
```

Windows에서는 `$env:WEB_BIND='0.0.0.0'` 같은 PowerShell 환경변수 문법을 사용합니다.
원격 접속은 localhost 대신 EC2 주소와 설정한 포트를 사용합니다.

AWS 리소스 생성, S3 업로드, SSM 원격 명령, OIDC 역할 생성, GitHub 배포 워크플로는 포함하지 않습니다.
예제 저장소의 AWS 계정/버킷/인스턴스 값을 복사하지 않았습니다.
현재 요청의 Windows/Linux 스크립트는 컨테이너 실행 자동화를 담당합니다.

CloudWatch/S3 전송을 원하면 `AWS_REGION`, `COLLECTION_S3_BUCKET`, `COLLECTION_LOG_GROUP`,
`COLLECTION_LOG_STREAM`을 호스트 환경에 지정하세요(Compose가 API 컨테이너에 전달).
자격증명은 EC2 IAM 역할 등 boto3 기본 체인을 통해 별도로 제공해야 합니다.
호스트 AWS 프로필 파일은 이 구성에서 컨테이너로 자동 전달되지 않습니다.
비밀키를 Dockerfile/Compose/Git에 넣지 마세요. AWS 미설정 시 SQLite 저장만 동작하고 전송은 disabled입니다.

## 검증 범위

2026-11-02 Windows Docker Desktop의 Linux 엔진에서 PowerShell 배포 스크립트의
실제 이미지 빌드, 테스트, 모델 배치, 웹/API 기동을 완료했습니다.
Python 65개, 웹 53개 테스트와 TypeScript/Vite 빌드가 통과했습니다.
웹 프록시를 통한 예측 조회, 입력 저장, T/F 및 숫자 정답 저장을 확인했고,
컨테이너를 강제 재생성한 뒤에도 동일 접수번호의 입력/예측/정답/등록 시각이 유지됐습니다.
두 컨테이너 모두 healthy이며 기본 접속 주소는 http://localhost:8080 입니다.

현재 검증 릴리스는 `container-check-20261102`입니다. 기존 컨테이너를 단순 시작/정지하려면
프로젝트 루트에서 `docker compose start` / `docker compose stop`을 사용하세요.
동일 이미지로 컨테이너를 재생성하려면 다음처럼 릴리스를 지정합니다.

```powershell
$env:RELEASE='container-check-20261102'
docker compose up -d --no-build --wait
```

새 버전을 빌드할 때는 위의 배포 스크립트를 사용하세요.
Linux Bash 스크립트는 문법/모의 실행 흐름만 확인했으며 별도 Linux 호스트에서 전체 배포를
실행한 것은 아닙니다. AWS 실제 배포/전송 확인도 수행하지 않았습니다.
자세한 결과는 [container-verification.md](container-verification.md)를 참고하세요.

참고: https://github.com/yeonsung-cloud-mlops/demo_usedcars/blob/8089742422bbdbad51ff064789034743926fda6a/.github/workflows/deploy.yml
