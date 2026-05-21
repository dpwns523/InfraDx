# Skill: gather-context

## Trigger
- `session.domain` is set
- `session.spec` is incomplete

## Input
- `session.domain`: server | network | disk | kubernetes | cloud

## Action
Ask for system specification fields **one group at a time** (not all at once).

---

### Domain: server

**Step 1** — Deployment type
```
서버 유형을 선택해 주세요:
  [1] 베어메탈 (물리 서버)
  [2] 가상머신 (VM)
  [3] 컨테이너 (Docker/K8s)
```

If VM → ask hypervisor: KVM / VMware ESXi / Microsoft Hyper-V / IBM LPAR / 기타

**Step 2** — OS
```
운영체제를 알려주세요 (명령어 결과 붙여넣기):

Linux:  uname -a
AIX:    oslevel -s && uname -a
Other:  직접 입력
```

Parse kernel version from output. Store:
- `spec.os_type`: linux | aix | windows | other
- `spec.kernel_version`: e.g., `5.15.0-91-generic`
- `spec.arch`: x86_64 | aarch64 | ppc64le

**Step 3** — Resources (Linux)
```
CPU/메모리 정보를 알려주세요:
  lscpu | grep -E "^CPU\(s\)|Model name|Architecture"
  free -h
```

---

### Domain: network

**Step 1** — Problem layer
```
문제가 발생하는 네트워크 계층을 선택해 주세요:
  [1] L2 — MAC, VLAN, spanning tree
  [2] L3 — IP 라우팅, 서브넷
  [3] L4 — TCP/UDP 포트, 방화벽
  [4] L7 — HTTP/HTTPS, DNS, 애플리케이션 프로토콜
  [5] 모름
```

**Step 2** — Endpoints
```
출발지 IP와 목적지 IP/호스트명을 알려주세요.
```

**Step 3** — Devices involved
```
관련 네트워크 장비를 알려주세요 (해당하는 것만):
- NIC 모델 및 드라이버
- 스위치/라우터 벤더 및 모델
- 방화벽/로드밸런서 (있는 경우)
```

---

### Domain: disk

**Step 1** — Disk type
```
스토리지 유형을 선택해 주세요:
  [1] 내장 디스크 (Internal) — 서버에 직접 장착
  [2] 외장 스토리지 — SAN / NAS / DAS
```

**Step 2** — Interface & media
```
인터페이스와 미디어 타입을 알려주세요:
  인터페이스: NVMe / SATA / SAS / FC / iSCSI
  미디어:     SSD / HDD / NVMe SSD
  RAID:       없음 / RAID 레벨 / 벤더 RAID 카드
```

**Step 3** — Current layout
```
현재 디스크 구성을 확인해 주세요:
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
  df -hT
```

---

### Domain: kubernetes

**Step 1** — Cluster distribution
```
Kubernetes 배포 유형을 선택해 주세요:
  [1] EKS       — AWS 관리형
  [2] GKE       — GCP 관리형
  [3] AKS       — Azure 관리형
  [4] Self-managed — kubeadm / Rancher / OpenShift / k3s
  [5] 기타
```

**Step 2** — Cluster & workload info
```
다음 정보를 알려주세요:

kubectl version --short
kubectl get nodes -o wide
```

Store:
- `spec.k8s_distribution`: eks | gke | aks | self-managed | other
- `spec.k8s_version`: e.g., `1.29.3`
- `spec.node_count` / `spec.node_type`

**Step 3** — Problem scope
```
문제가 발생한 영역을 선택해 주세요:
  [1] Pod / 컨테이너  — CrashLoopBackOff, OOMKilled, 시작 실패
  [2] 네트워크 정책   — Service, Ingress, NetworkPolicy, DNS
  [3] 스토리지       — PVC, PV, StorageClass
  [4] 스케줄링       — Pending, Affinity, Taint/Toleration, HPA
  [5] 보안/권한      — RBAC, ServiceAccount, Secret
  [6] 노드           — NotReady, 자원 부족, DaemonSet
```

**Step 4** — Namespace & resource name
```
문제가 발생한 네임스페이스와 리소스 이름을 알려주세요:
  kubectl get pods -n <namespace> | grep -v Running
  kubectl describe <resource> <name> -n <namespace> | tail -30
```

---

### Domain: cloud

**Step 1** — Cloud provider
```
클라우드 프로바이더를 선택해 주세요:
  [1] AWS   — Amazon Web Services
  [2] GCP   — Google Cloud Platform
  [3] Azure — Microsoft Azure
  [4] NCP   — Naver Cloud Platform
  [5] KT Cloud / NHN Cloud / 기타
```

Store: `spec.cloud_provider`: aws | gcp | azure | ncp | other

**Step 2** — Service type
```
문제가 발생한 서비스 유형을 선택해 주세요:

AWS:   EC2 / ECS / EKS / Lambda / RDS / S3 / ALB/NLB / VPC / CloudFront / IAM
GCP:   GCE / GKE / Cloud Run / Cloud SQL / GCS / Load Balancer / IAM
Azure: VM / AKS / App Service / Azure SQL / Blob / Load Balancer / AD
NCP:   Server / Kubernetes / Cloud DB / Object Storage / Load Balancer
```

Store: `spec.cloud_service`: e.g., `EC2`, `RDS`, `ALB`

**Step 3** — Region & account info
```
다음 정보를 알려주세요:
- 리전 (예: ap-northeast-2)
- 계정/프로젝트 ID (선택, 민감정보 제외)
- 멀티 AZ / 단일 AZ 구성 여부
```

**Step 4** — Cloud-specific diagnostics
Depending on provider and service:

#### AWS
```bash
# EC2 상태
aws ec2 describe-instance-status --instance-ids <id>
# VPC/보안그룹
aws ec2 describe-security-groups --group-ids <sg-id>
# ALB 타겟 상태
aws elbv2 describe-target-health --target-group-arn <arn>
# CloudWatch 로그
aws logs tail <log-group> --since 1h
# IAM 권한 검증
aws iam simulate-principal-policy --policy-source-arn <arn> --action-names <action>
```

#### GCP
```bash
# GCE 인스턴스 상태
gcloud compute instances describe <name> --zone <zone>
# 방화벽 규칙
gcloud compute firewall-rules list --filter="network=<vpc>"
# 로드밸런서 백엔드 상태
gcloud compute backend-services get-health <name> --global
# Cloud Logging
gcloud logging read "resource.type=gce_instance" --limit 50
```

#### Azure
```bash
# VM 상태
az vm show -g <rg> -n <name> --query instanceView
# NSG 규칙
az network nsg rule list -g <rg> --nsg-name <nsg>
# Load Balancer 상태
az network lb show -g <rg> -n <lb>
```

---

## Output
- Populates `session.spec` object
- Transitions to `describe-symptom` (inline in AGENT.md Phase 3)

## Validation
- OS parse failure → ask user to paste raw output again
- Unknown vendor/model → store as-is, note for knowledge base lookup
- Cloud: 민감 정보(계정 키, 비밀번호)는 요청하지 않음 — 리소스 ID/ARN만 요청
