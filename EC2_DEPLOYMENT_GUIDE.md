# Goldhome EC2 배포 설명서

**대상** 처음 AWS에서 서버를 만들고 GitHub 프로젝트를 실행하는 팀원

**완료 기준** 내 PC 브라우저에서 새 EC2의 예측 화면이 열리고, 입력을 저장한 뒤 접수번호로 다시 조회할 수 있다. AWS 수집까지 확인하는 경우 S3와 CloudWatch에서 새 이벤트를 찾는다.

저장소 [kjh3847/gold-price-forecast](https://github.com/kjh3847/gold-price-forecast) · 기준 [main의 d49e0e4 커밋](https://github.com/kjh3847/gold-price-forecast/commit/d49e0e494bc16b4625ff60f8e6dddcd759ef6d68) · 2026-11-16 KST 확인

명령은 **코드 블록 하나씩** 붙여넣고 실행하세요. 오류가 뜨면 해당 단계에서 멈추고 아래 오류 표를 확인하세요. **PowerShell**은 내 Windows PC의 창이고, **EC2 터미널**은 SSH로 연결한 Ubuntu 창입니다. AWS 콘솔 작업은 브라우저에서 합니다.

## 1. 계정과 권한 준비

- [AWS 콘솔](https://console.aws.amazon.com/)에 로그인합니다. 팀 AWS 계정을 쓴다면 실습용 EC2를 생성하고 보안 그룹을 편집할 권한이 필요합니다. 이 GitHub 저장소는 공개 상태라 코드를 받는 데 GitHub 로그인이 필요하지 않습니다.
- 팀 AWS 계정에서 권한 오류가 뜨면 계정 관리자에게 아래 문장을 보내세요. 개인 AWS 계정을 쓰는 경우 계정의 요금과 사용 가능한 인스턴스 유형을 먼저 확인하세요.
- 기존 팀 서버에 실수로 작업하지 않도록 새 인스턴스 이름에 본인 이니셜을 넣으세요. 이전 서버의 IP와 키 대신 이번에 만드는 인스턴스 정보를 사용합니다.

> 서울 리전에 Goldhome 실습용 EC2 한 대를 만들려고 합니다. 인스턴스와 키 페어를 생성하고, 새 보안 그룹에 제 공인 IP의 SSH(22) 및 팀 확인용 웹(8080) 규칙을 설정할 수 있도록 권한을 주시거나 리소스 생성을 부탁드립니다. AWS 이벤트 수집도 검증하는 경우 테스트용 S3 버킷·CloudWatch 로그 스트림·EC2 역할을 함께 준비해 주세요.

## 2. AWS 콘솔에서 EC2 만들기

1. 콘솔 오른쪽 위 리전을 **아시아 태평양(서울) · ap-northeast-2**로 바꿉니다.
2. 콘솔 위쪽 검색창에 **EC2**를 입력합니다. 왼쪽 메뉴 **인스턴스 → 인스턴스 시작(Launch instances)**을 누릅니다.
3. 아래 표대로 선택합니다. AWS 콘솔 언어에 따라 한글 또는 영문 항목이 보일 수 있습니다.

| 화면 항목 | 선택할 값 |
|---|---|
| 이름(Name) | `goldhome-demo-본인이니셜` |
| 애플리케이션 및 OS 이미지(AMI) | Canonical **Ubuntu Server 24.04 LTS**, **64-bit (x86)** |
| 인스턴스 유형(Instance type) | **t3.medium** 권장. 테스트와 이미지 빌드까지 이 서버에서 실행하므로 메모리 4 GiB 기준으로 안내합니다. |
| 키 페어(Key pair) | **새 키 페어 생성 → 이름 goldhome-demo → RSA → .pem → 키 페어 생성** |
| VPC 및 서브넷 | 실습용 기본 VPC가 있으면 기본 VPC와 서브넷을 사용합니다. 팀에서 지정한 VPC라면 인터넷 게이트웨이 경로가 있는 퍼블릭 서브넷을 선택합니다. |
| 퍼블릭 IP 자동 할당 | **활성화(Enable)** |
| 방화벽(Security groups) | **보안 그룹 생성 → SSH 트래픽 허용 → 내 IP(My IP)**. 새 Ubuntu의 SSH 포트는 TCP 22입니다. 웹 규칙은 아래에서 추가합니다. |
| 스토리지 구성 | 루트 볼륨 **20 GiB, gp3** 권장. 암호화 선택란이 있으면 활성화합니다. |
| 인스턴스 수 | **1** |

4. 새 키를 만들면 `goldhome-demo.pem`이 내려받아집니다. `다운로드` 폴더에 보관하세요. 개인 키 파일은 다시 내려받을 수 없으므로 각자 생성한 키를 보관합니다.
5. **인스턴스 시작**을 누르고 **모든 인스턴스 보기**로 이동합니다. 새 인스턴스가 **실행 중(Running)**이고 상태 검사에 통과할 때까지 기다립니다.
6. 인스턴스를 선택한 뒤 세부 정보에서 **퍼블릭 IPv4 주소**를 복사합니다. 실습 기록에는 인스턴스 이름과 리전도 적어 둡니다.

인스턴스 유형과 볼륨 크기는 문서의 실습 권장값이며 요금이 발생할 수 있습니다. [AWS EC2 시작 가이드](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html)

## 3. 보안 그룹에 웹 접속 규칙 추가하기

1. **EC2 → 인스턴스 → 방금 만든 인스턴스 → 보안(Security)** 탭을 엽니다.
2. **보안 그룹**에 표시된 `sg-…` 링크를 누릅니다. **인바운드 규칙 → 인바운드 규칙 편집 → 규칙 추가**를 누릅니다.
3. 기존 SSH 규칙을 확인하고 아래의 TCP 8080 규칙을 추가한 뒤 **규칙 저장**을 누릅니다.

| 용도 | 유형 | 포트 | 소스 |
|---|---|---:|---|
| 내 PC에서 서버 관리 | SSH | 22 | **내 IP(My IP)** |
| 내 PC에서 웹 화면 열기 | 사용자 지정 TCP(Custom TCP) | 8080 | **내 IP(My IP)** |
| 다른 팀원이 브라우저로 확인할 때 | 사용자 지정 TCP(Custom TCP) | 8080 | 그 팀원의 **공인 IPv4/32**. 팀원별로 한 줄씩 추가합니다. |

다른 팀원에게는 “EC2 화면 확인에 사용할 네트워크의 **공인 IPv4**를 알려줘”라고 요청하세요. 콘솔에서 **내 IP**를 선택하면 현재 AWS 콘솔을 연 PC의 IP가 들어갑니다. 집이나 핫스팟처럼 접속 위치가 바뀌면 새 공인 IP로 규칙을 갱신합니다.

이 프로젝트에는 쓰기 API도 있으므로 위 표처럼 허용 대상을 지정합니다. 아웃바운드는 설치에 필요한 GitHub·Docker·패키지 저장소에 HTTPS로 접근할 수 있어야 합니다. FastAPI는 Docker 내부의 8000 포트를 사용합니다. 브라우저와 API 요청은 모두 외부 8080으로 들어옵니다. [AWS 보안 그룹 규칙 예시](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html)

## 4. 내 PC에서 SSH 접속하기

**Windows PowerShell**을 열고 다음을 실행하세요. 첫 줄을 아까 복사한 EC2 주소로 바꿉니다. 키를 다른 폴더에 저장했다면 둘째 줄의 경로도 수정합니다.

```powershell
$ec2Ip = '여기에-EC2-퍼블릭-IPv4'
$goldKey = Join-Path $env:USERPROFILE 'Downloads\goldhome-demo.pem'
Test-Path -LiteralPath $goldKey
```

`True`가 나오면 아래를 실행합니다. 처음 접속할 때 서버 지문 확인 질문이 나오면 AWS 콘솔의 **인스턴스 → 작업 → 모니터링 및 문제 해결 → 시스템 로그 가져오기**에서 `SSH HOST KEY FINGERPRINTS`를 찾아 지문을 비교하고, 일치하면 `yes`를 입력합니다.

```powershell
ssh -i "$goldKey" -p 22 "ubuntu@$ec2Ip"
```

**성공 확인** 터미널 왼쪽이 `ubuntu@ip-…:~$` 형태로 바뀝니다. 이제 이 창에 입력하는 명령은 EC2에서 실행됩니다. 연결을 끊으려면 `exit`를 입력합니다. 팀에서 제공한 기존 서버에 접속할 때는 관리자가 알려준 SSH 사용자와 포트를 사용하세요. [AWS SSH 접속 안내](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/connect-linux-inst-ssh.html)

## 5. EC2에 Docker와 Git 설치하기

이 단계부터 명령은 **EC2 터미널**에 붙여넣습니다. 새 Ubuntu 24.04 기준입니다.

### 5-1. 도구 설치

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
```

### 5-2. Docker 패키지 저장소 등록

아래 블록 전체를 붙여넣습니다. 마지막 `EOF`까지 들어가야 합니다.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<'EOF'
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

### 5-3. Docker Engine과 Compose 설치 및 확인

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
sudo docker run --rm hello-world
```

**성공 확인** `Docker Compose version`과 `Hello from Docker!`가 표시됩니다. Python과 Node.js는 프로젝트가 Docker 이미지 안에서 설치합니다. [Docker 공식 설치 안내](https://docs.docker.com/engine/install/ubuntu/)

## 6. GitHub에서 코드를 받고 배포 설정하기

### 6-1. 저장소 가져오기

**EC2 터미널**에서 실행합니다. GitHub의 `main`을 받은 뒤 이 설명서가 확인한 커밋을 선택해 팀원이 같은 버전으로 실습할 수 있게 합니다.

```bash
cd ~
git clone --branch main --single-branch https://github.com/kjh3847/gold-price-forecast.git
cd ~/gold-price-forecast
git switch --detach d49e0e494bc16b4625ff60f8e6dddcd759ef6d68
git rev-parse --short HEAD
ls -l compose.yaml deploy/deploy.sh
```

**성공 확인** `d49e0e4`와 두 파일 이름이 출력됩니다. `detached HEAD` 안내는 지정한 커밋을 그대로 실행할 때 나오는 정상 메시지입니다. 이미 같은 이름의 폴더가 있다면 지우기 전에 프로젝트 경로와 커밋부터 확인합니다.

### 6-2. 웹 포트 지정하기

**새 설치에서 한 번** 실행합니다. `.env`는 배포 설정 파일입니다. 이미 AWS 수집 설정을 넣은 파일이 있다면 이 블록 대신 `nano .env`로 열고 `WEB_BIND`, `WEB_PORT` 두 줄만 수정하세요.

```bash
cat > .env <<'EOF'
WEB_BIND=0.0.0.0
WEB_PORT=8080
AWS_REGION=ap-northeast-2
COLLECTION_S3_BUCKET=
COLLECTION_LOG_GROUP=
COLLECTION_LOG_STREAM=
EOF
chmod 600 .env

sudo bash deploy/deploy.sh 2026-09-24 --check-only
```

**성공 확인** `Prerequisites and Compose configuration OK`가 표시됩니다. `WEB_BIND`를 지정하면 허용된 팀원 PC가 EC2의 8080에 접속할 수 있습니다. AWS 수집 변수의 빈칸은 기본 실습에서 SQLite에 저장하는 설정입니다.

## 7. 배포 실행하기

**EC2 터미널**에서 실행합니다. 테스트와 이미지 빌드가 끝날 때까지 창을 열어 두세요. 첫 배포는 패키지 다운로드와 모델 계산 시간이 필요합니다.

```bash
cd ~/gold-price-forecast
sudo bash deploy/deploy.sh 2026-09-24
```

스크립트가 **Python 테스트 → 웹 테스트·빌드 → 예측 데이터 생성 → 웹/API 실행 → API 응답 확인**을 차례로 수행합니다. 아래와 같이 `Deployment OK`가 뜨면 다음 단계로 갑니다.

```text
Deployment OK: release=run-... forecast-request=2026-09-24
```

`2026-09-24`는 저장소에 포함된 가격 CSV의 마지막 날짜입니다. 새 EC2에서도 이 날짜를 입력해야 같은 데이터로 배포할 수 있습니다. PC를 끄거나 SSH를 종료한 뒤에도 실행 중인 컨테이너는 EC2에서 계속 동작합니다.

## 8. 다른 PC에서 실행 결과 검증하기

### 8-1. EC2 내부 확인

```bash
cd ~/gold-price-forecast
sudo docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/forecast/latest
```

두 컨테이너 상태에 `healthy`가 표시되고 상태 확인 응답에 `"status":"ok"`가 나오면 정상입니다. 예측 응답에서 `2026-09-24`를 확인합니다.

### 8-2. Windows 브라우저에서 확인

1. 내 PC 브라우저 주소창에 `http://EC2의-퍼블릭-IPv4:8080`을 입력합니다. IPv4와 `8080` 사이에 **콜론(:)**을 넣으세요.
2. `/api/health`를 붙인 주소도 열어 `{"status":"ok"}`가 보이는지 확인합니다.
3. 메인 화면에 **예측 기준일 2026-09-24**와 **향후 5거래일 예측 그래프 또는 예상 범위**가 표시되는지 봅니다. 오래된 CSV 안내 팝업이 뜨면 닫고 초기 화면을 확인할 수 있습니다.
4. **입력값 · 매수 기록 · 실제 정답** 영역의 **저장할 주간 금액 (원)**에 `100000`을 넣고 **저장할 상품**에서 하나를 선택합니다. **입력값과 예측 저장**을 누릅니다. 표시된 **접수번호**를 복사한 뒤 **접수 기록 조회**를 눌러 접수 내용과 저장된 예측이 표시되는지 확인합니다. 접수번호를 다른 브라우저에 붙여넣어 다시 조회해도 됩니다.
5. 실습 DB에서 정답 저장도 시험할 경우 접수를 조회한 뒤 **정답 입력 방식**에서 **T/F** 또는 **실제 종가**를 고릅니다. 접수에 표시된 대상일이 이미 지났다면 테스트 값을 넣고 **실제 정답 저장**을 누릅니다. 같은 접수번호로 다시 조회한 뒤 검증 기록에 합성 입력임을 표시합니다.
6. 다른 팀원이 확인할 때는 그 팀원의 IP가 3단계의 웹 규칙에 포함됐는지 확인한 뒤 동일한 웹 주소를 전달합니다.

## 9. 과제의 AWS 이벤트 수집까지 확인하는 경우

웹과 SQLite 저장 확인을 마친 뒤 진행합니다. 팀에서 준비한 버킷·로그 그룹·역할이 있으면 담당자에게 아래 값을 받아 **9-3부터** 진행할 수 있습니다. 이 경우 대상 EC2에 역할이 연결되어 있는지도 확인합니다.

> Goldhome 테스트 EC2에 연결할 IAM 역할 이름, 서울 리전 S3 버킷 이름, CloudWatch 로그 그룹과 스트림 이름을 알려주세요. 역할에 해당 버킷의 collection/ 경로 쓰기와 지정 스트림에 로그 쓰기 권한이 필요합니다.

### 9-1. 저장 대상 만들기

1. **S3 → 버킷 생성**에서 서울 리전의 범용 버킷을 만듭니다. 이름은 전역에서 고유해야 합니다. 예를 들어 `goldhome-demo-본인영문이니셜-임의숫자`로 정하고 **모든 퍼블릭 액세스 차단**을 유지합니다. 기본 암호화는 SSE-S3를 사용합니다.
2. **CloudWatch → 로그(Logs) → 로그 그룹 → 로그 그룹 생성**에서 `/gold-forecast/events`를 만듭니다. 같은 이름이 이미 있다면 배포에 사용할 그룹을 담당자와 확인합니다.
3. 새 로그 그룹을 열고 **로그 스트림 생성**으로 `ec2-api`를 추가합니다. 화면에서 실제 로그 그룹과 스트림 이름을 기록합니다.

### 9-2. EC2 실행 권한 연결하기

1. **IAM → 정책 → 정책 생성 → JSON**을 엽니다. 아래 값을 실제 값으로 바꿉니다. `BUCKET_NAME`은 S3 버킷 이름이고 `ACCOUNT_ID`는 해당 AWS 계정의 12자리 번호입니다. 그룹·스트림 이름을 다르게 만들었다면 ARN 마지막 경로도 수정합니다.
2. 정책 이름을 `GoldhomeCollectionWrite`로 지정하고 정책을 만듭니다.
3. **IAM → 역할 → 역할 생성 → AWS 서비스 → EC2**를 선택하고, 방금 만든 정책을 연결합니다. 역할 이름은 `GoldhomeDemoEc2Role`처럼 지정합니다.
4. **EC2 → 인스턴스 → 새 실습 인스턴스 → 작업 → 보안 → IAM 역할 수정**에서 만든 역할을 선택하고 저장합니다.
5. **EC2 → 인스턴스 → 작업 → 인스턴스 설정 → 인스턴스 메타데이터 옵션 수정**에서 메타데이터를 활성화하고 **IMDSv2 필수**, **응답 홉 제한 2**로 설정합니다. 이 설정으로 Docker 안의 API가 인스턴스 역할의 임시 자격증명을 사용할 수 있습니다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::BUCKET_NAME/collection/*"
    },
    {
      "Effect": "Allow",
      "Action": "logs:PutLogEvents",
      "Resource": "arn:aws:logs:ap-northeast-2:ACCOUNT_ID:log-group:/gold-forecast/events:log-stream:ec2-api"
    }
  ]
}
```

IAM 메뉴에서 권한 오류가 뜨면 1단계 요청 문구와 위 정책을 계정 관리자에게 전달합니다. [EC2 역할 연결](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/attach-iam-role.html) · [EC2 메타데이터 설정](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-options.html) · [CloudWatch Logs 권한](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/iam-identity-based-access-control-cwl.html)

### 9-3. 환경 설정 반영 후 새 이벤트 확인

1. EC2 터미널에서 아래 명령을 실행합니다.

```bash
cd ~/gold-price-forecast
nano .env
```

2. `COLLECTION_S3_BUCKET=` 오른쪽에 버킷 이름을 넣고, 나머지 두 줄을 `COLLECTION_LOG_GROUP=/gold-forecast/events`와 `COLLECTION_LOG_STREAM=ec2-api`로 채웁니다. 실제 만든 이름이 다르면 그 이름으로 입력합니다. `WEB_BIND`와 `WEB_PORT`는 그대로 둡니다. **Ctrl+O → Enter → Ctrl+X**로 저장하고 닫습니다.
3. **7단계 배포 명령을 다시 실행**한 뒤 화면에서 새 테스트 입력을 저장합니다. 정답 로그 검증이 필요하면 같은 접수에 합성 정답도 저장합니다.
4. 웹 화면의 저장 메시지에서 `s3=sent`와 `cloudwatch=sent`를 확인합니다. AWS 콘솔의 **S3 버킷 → collection/**에 새 JSON이 생기는지 확인합니다. **CloudWatch → /gold-forecast/events → ec2-api**에서 같은 접수번호와 시간대의 이벤트를 찾습니다. 입력은 `input_saved`, 정답은 `actual_saved`로 표시됩니다.
5. 저장은 성공했지만 이벤트가 안 보이면 아래 명령으로 API 로그를 확인합니다.

```bash
sudo docker compose logs --tail=100 api
```

`Delivery failed`가 있으면 버킷·로그 경로, IAM 역할, 리전, 메타데이터 홉 제한을 확인한 뒤 **새 테스트 입력**으로 다시 확인합니다. 화면의 접수번호가 발급됐다는 사실은 SQLite 저장을 확인해 줍니다. AWS 전송은 실제 S3 객체와 CloudWatch 로그를 열어 확인합니다.

## 10. 종료·재시작·버전 변경

| 하려는 일 | 방법 |
|---|---|
| EC2에서 웹과 API만 잠시 정지 | 프로젝트 폴더에서 `sudo docker compose stop` |
| 이전에 배포한 웹과 API 다시 시작 | 같은 폴더에서 `sudo docker compose start`를 실행하고 `sudo docker compose ps`로 확인 |
| EC2 실습을 끝내고 비용 줄이기 | AWS 콘솔 **인스턴스 상태 → 인스턴스 중지(Stop)**. EC2가 정지해도 EBS 등 사용 중인 리소스 비용은 남을 수 있습니다. |
| 중지했던 EC2에서 서비스 재확인 | AWS 콘솔에서 **시작(Start)** 후 새 **퍼블릭 IPv4**를 확인합니다. SSH 재접속 후 `sudo docker compose ps`를 실행하고, 컨테이너가 정지 상태면 `sudo docker compose start`를 실행합니다. |
| 팀에서 승인한 최신 `main` 버전 배포 | `git fetch origin main` → `git switch --detach FETCH_HEAD` → `git rev-parse HEAD` → 7단계 배포 명령. 대상 코드의 초기 가격 파일 날짜가 바뀌었으면 배포 날짜도 확인합니다. |

사용자 입력과 예측 데이터는 EC2의 Docker 볼륨 `gold-forecast_gold-data`에 보관됩니다. 컨테이너를 멈추거나 다시 시작해도 저장 데이터는 유지됩니다. **`docker compose down -v`는 이 볼륨을 지웁니다.** 기존 팀 인스턴스의 데이터를 보존해야 한다면 새 인스턴스에 배포하거나 백업 후 변경하세요.

## 11. 자주 막히는 곳

| 증상 | 먼저 할 일 |
|---|---|
| `Test-Path`가 `False` | 다운로드한 `.pem` 파일 이름과 위치를 확인한 후 PowerShell의 `$goldKey` 값을 수정합니다. |
| `Permission denied (publickey)` | 사용자 이름이 `ubuntu`인지, 키 파일이 그 인스턴스 생성 때 선택한 키 페어인지 확인합니다. |
| `UNPROTECTED PRIVATE KEY FILE` | 내 PC에서 PEM 파일 우클릭 → **속성 → 보안 → 고급 → 상속 사용 안 함**. 내 Windows 계정의 읽기 권한을 유지하고 다른 사용자에게 부여된 접근 권한을 제거한 뒤 SSH를 다시 시도합니다. |
| SSH가 `Connection timed out` | 인스턴스가 실행 중이고 상태 검사를 통과했는지, 현재 퍼블릭 IPv4가 맞는지, 보안 그룹 TCP 22의 소스가 현재 내 공인 IP인지 확인합니다. |
| EC2에서 `curl`은 되는데 내 브라우저만 접속 불가 | 주소가 `http://IP:8080`인지와 보안 그룹의 TCP 8080 규칙을 확인합니다. `sudo docker compose ps`의 포트가 `0.0.0.0:8080->8080/tcp`인지도 봅니다. |
| `sudo docker compose` 실행 시 파일을 못 찾음 | `cd ~/gold-price-forecast`로 이동한 뒤 다시 실행합니다. |
| 빌드 도중 `No space left on device` 또는 `Killed` | `df -h /`로 여유 디스크, `free -h`로 메모리를 확인합니다. 공간이면 루트 볼륨, 메모리 부족이면 인스턴스 유형을 담당자와 확인합니다. |
| 컨테이너가 `unhealthy` 또는 화면에 예측이 없음 | `sudo docker compose logs --tail=100 api web`을 확인합니다. 배포에 준 날짜와 저장소 CSV 마지막 날짜가 맞는지 보고 7단계를 다시 실행합니다. |
| CSV 업로드 시 `413 Request Entity Too Large` | 기준 버전의 Nginx 기본 요청 크기에 걸릴 수 있습니다. 화면이 요구한 기간을 포함하는 더 작은 CSV로 다시 시도하고, API의 CSV 제한인 2 MB도 확인합니다. |
| 웹에서 저장 후 최신 데이터로 다시 시도하라는 안내가 뜸 | 화면을 새로고침해 서버의 최신 예측 기준일을 불러온 다음 저장합니다. |

## 12. 팀원 검증 기록

배포한 팀원이 아래 항목을 채우면 같은 버전에서 어디까지 확인했는지 알 수 있습니다. `git rev-parse HEAD`와 `sudo docker compose version`은 EC2 터미널에서 실행합니다.

```text
작업자 / 배포일(KST) =
EC2 리전 / Ubuntu 버전 / 인스턴스 유형 =
Git 커밋 =
Docker Compose 버전 =
웹·API healthy / 브라우저 화면 =
예측 기준일 및 5거래일 그래프 =
입력 저장·접수번호 재조회 =
정답 저장·재조회 =
S3 객체·CloudWatch 로그 = 확인 / 미실행 / 실패
막힌 단계 / 오류 문구 / 해결 방법 =
```

배포 명령과 경로는 위 GitHub 기준 커밋에서 확인했습니다. 기존 EC2에서 확인한 배포 사례와 기준 커밋의 자동 테스트는 아래 링크에서 볼 수 있습니다. 이 설명서를 따라 새 EC2에서 실행한 결과는 위 양식에 남깁니다. [기존 EC2 배포 기록](https://github.com/kjh3847/gold-price-forecast/blob/d49e0e494bc16b4625ff60f8e6dddcd759ef6d68/deploy/container-verification.md) · [기준 커밋의 GitHub Actions 테스트](https://github.com/kjh3847/gold-price-forecast/actions/runs/42586046659)
