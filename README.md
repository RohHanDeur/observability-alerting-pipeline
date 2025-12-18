# Observability Alerting Pipeline (Prometheus → Alertmanager → Slack/Webhook, Grafana)

<!--
[목적]
- 로컬 환경에서 Prometheus 규칙(alert rules) 기반 알림을 생성하고,
  Alertmanager를 통해 Slack 및 Webhook(FastAPI)으로 전달되는 end-to-end 파이프라인을 구성한 프로젝트.
- 운영 관점에서 "기동 / 검증 / 트러블슈팅 / 종료"까지 한 번에 재현 가능하도록 문서화.

[구성 요소]
- Prometheus: Metrics 수집 + Alert Rules 평가
- Alertmanager: Alert 라우팅/그룹핑/중복제거 + Receiver(Slack/Webhook)로 전달
- Grafana: Metrics 시각화 (대시보드 직접 구성/임포트는 선택)
-->

---

## 1. Repository 구조

<!--
- 이 구조를 유지하면 문서의 모든 명령어가 그대로 동작합니다.
- alertmanager.yml에 Slack Webhook이 비어있어도 시스템 구동/연결 검증은 가능하며,
  Slack 실제 수신까지 보려면 webhook을 유효하게 넣어야 합니다.
-->

```text
observability-alerting-pipeline/
├── docker-compose.monitoring.yml
└── monitoring/
    ├── prometheus.yml
    ├── alerts.yml
    └── alertmanager.yml
```
## 2. 사전 요구사항 (Prerequisites)

```text
<!-- 필수: - Docker Desktop (macOS/Windows) 또는 Docker Engine (Linux) - docker compose (Docker v2 이상) 추가(권장): - jq: Prometheus API 결과를 보기 좋게 출력 - macOS: brew install jq - Ubuntu: sudo apt-get install -y jq -->
```
## 2.1 버전 확인
```text
docker --version
docker compose version
```
## 3. 설정 파일 요약
```text
<!-- 각 파일의 역할을 "면접/리뷰 관점에서" 빠르게 설명할 수 있도록 요약합니다. -->
```
## 3.1 docker-compose.monitoring.yml
```text
Prometheus(9090), Alertmanager(9093), Grafana(3000) 컨테이너 기동

Prometheus는 ./monitoring/prometheus.yml, ./monitoring/alerts.yml를 컨테이너 내부로 마운트
```
## 3.2 monitoring/prometheus.yml
```text
scrape_interval: 5s로 빠르게 수집/알림 확인

rule_files로 alerts.yml 로드

alerting.alertmanagers.targets로 Alertmanager 연결 (alertmanager:9093)

scrape_configs로 FastAPI 앱의 metrics 수집 (host.docker.internal:8000/metrics)
```
## 3.3 monitoring/alerts.yml
```text
High5xxErrorRate: /fail handler의 5xx 비율이 1% 초과가 10초 지속되면 firing

HighP95Latency: p95 > 200ms가 1분 지속되면 firing
```
## 3.4 monitoring/alertmanager.yml
```text
알림 그룹핑/반복 전송 정책(route)

receiver: default

slack_configs: Slack 채널로 알림

webhook_configs: FastAPI 엔드포인트(/alertmanager)로 알림
```
## 4. 시스템 기동 방법 (Start)
```text
<!-- 핵심: - Prometheus는 FastAPI 앱(8000)이 있어야 scrape target이 UP이 됩니다. - FastAPI 앱을 먼저 띄우고 monitoring stack을 올리는 흐름이 가장 깔끔합니다. -->
## 4.1 (선택) FastAPI 앱이 이미 실행 중인지 확인
curl -s http://127.0.0.1:8000/metrics | head


응답이 나오면 FastAPI 앱이 떠있는 상태입니다.

응답이 없다면 FastAPI 앱을 먼저 실행하세요.
```
## 4.2 Monitoring Stack 기동
```text
cd observability-alerting-pipeline
docker compose -f docker-compose.monitoring.yml up -d --force-recreate
docker compose -f docker-compose.monitoring.yml ps


정상 상태 예시:

prometheus: Up

alertmanager: Up

grafana: Up
```
## 4.3 접속 URL
```text
Prometheus: http://localhost:9090

Alertmanager: http://localhost:9093

Grafana: http://localhost:3000
```
## 5. 검증 단계 (Validation)
```text
<!-- 검증은 "연결 검증 → 스크랩 검증 → 룰 로드 검증 → 알림 firing 검증 → receiver 전달 검증" 순서가 좋습니다. -->
## 5.1 컨테이너 상태 확인
docker compose -f docker-compose.monitoring.yml ps
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | egrep 'prometheus|alertmanager|grafana'
```
## 5.2 Prometheus → Alertmanager 연결 확인
```text
curl -s http://127.0.0.1:9090/api/v1/alertmanagers


activeAlertmanagers에 값이 나오면 Prometheus가 Alertmanager를 인지한 상태입니다.

추가로 컨테이너 내부에서 readiness 확인:

docker exec -it sre-starter-prometheus sh -lc 'wget -qO- http://alertmanager:9093/-/ready || true'


정상: OK

컨테이너명이 sre-starter-prometheus가 아니라면 docker compose ps로 이름 확인 후 바꾸세요.
```
## 5.3 Prometheus scrape target UP 확인
```text
Prometheus UI:

http://localhost:9090/targets

CLI로도 확인:

curl -s 'http://127.0.0.1:9090/api/v1/targets' | jq -r '
.data.activeTargets[]
| "\(.labels.job)\t\(.scrapeUrl)\t\(.health)"'


정상 기대:

sre-starter job이 UP

만약 DOWN이면:

FastAPI 앱이 8000에서 떠 있는지

macOS/Windows라면 host.docker.internal 접근이 되는지 확인
```
## 5.4 Alert Rules 로드 확인
```text
Prometheus UI:

http://localhost:9090/rules

CLI:

curl -s 'http://127.0.0.1:9090/api/v1/rules' | jq -r '
.data.groups[].rules[]
| select(.type=="alerting")
| "\(.name)\t\(.state)"'
```
## 6. 알림 트리거(발생) 및 전달 확인
```text
<!-- - High5xxErrorRate는 /fail로 요청을 계속 보내면 쉽게 firing 됩니다. - 알림이 firing 되면, 1) Prometheus에서 firing 확인 2) Alertmanager에서 alerts 확인 3) Alertmanager logs에서 notify success 확인 4) Slack / webhook 수신 확인 -->
6.1 5xx 알림 트리거 (High5xxErrorRate)
while true; do curl -s -o /dev/null http://127.0.0.1:8000/fail; sleep 0.2; done


중지: Ctrl + C
```
## 6.2 Prometheus에서 firing 확인
```text
curl -s http://127.0.0.1:9090/api/v1/alerts | jq -r '.data.alerts[] | "\(.labels.alertname)\t\(.state)"'


예상:

High5xxErrorRate firing
```
## 6.3 Alertmanager에서 alerts 확인
```text
curl -s http://127.0.0.1:9093/api/v2/alerts | jq -r '.[].labels.alertname'


예상:

High5xxErrorRate
```
## 6.4 Alertmanager 로그에서 notify 성공 확인
```text
docker logs -f sre-starter-alertmanager | egrep -i 'notify|slack|webhook|error|warn|dispatch'


예상 로그 예시:

Notify success ... integration=webhook[0]

(Slack 설정이 유효하면) Notify success ... integration=slack[0]
```
## 6.5 Webhook(FastAPI) 수신 확인
```text
FastAPI 쪽 로그에서 아래처럼 들어오면 정상:

ALERTMANAGER_WEBHOOK: { ... }
```
## 7. 트러블슈팅 체크리스트
```text
<!-- 현업에서 제일 많이 터지는 포인트만 골라서 정리합니다. -->
```
## 7.1 Prometheus 컨테이너가 계속 재시작 시
```text
prometheus.yml / alerts.yml YAML 문법 오류 가능

컨테이너 로그 확인:

docker logs --tail=200 sre-starter-prometheus
```
## 7.2 Alertmanager가 Prometheus에 확인 불가 한 경우
```text
prometheus.yml의 alertmanagers targets가 올바른지 확인 (alertmanager:9093)

네트워크/서비스명이 일치하는지 확인

Prometheus API로 확인:

curl -s http://127.0.0.1:9090/api/v1/alertmanagers
```
## 7.3 Target이 DOWN인 경우
```text
FastAPI 앱이 8000에서 실행 중인지 확인

metrics endpoint가 실제로 /metrics인지 확인

host.docker.internal이 환경에서 지원되는지 확인

macOS/Windows: 일반적으로 지원

Linux: 별도 설정 필요할 수 있음 (예: host-gateway 사용)
```
## 7.4 Slack 알림이 안오는 경우
```text
alertmanager.yml의 slack_configs api_url이 유효한지

channel 이름/권한 문제인지

Alertmanager logs에서 Notify success integration=slack가 찍히는지 확인

## 8. 종료 / 정리 (Stop)
docker compose -f docker-compose.monitoring.yml down


볼륨/이미지까지 정리(선택):

docker compose -f docker-compose.monitoring.yml down --volumes --remove-orphans
```
