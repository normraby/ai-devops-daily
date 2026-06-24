"""Original educational content for slides — all authored for this channel.

No third-party images, scraped documentation, or copyrighted assets.
Code examples are minimal teaching snippets (standard patterns, original wording).
Charts are illustrative visualizations aligned with narration, not third-party surveys.
"""

from __future__ import annotations

import re
from typing import Any

COMPLIANCE_FOOTER = (
    "Original educational content · Illustrative visuals where noted · "
    "Not affiliated with vendors mentioned"
)
CHART_DISCLAIMER = "Illustrative chart aligned with episode narration · Not third-party survey data"
CASE_STUDY_NOTE = "Hypothetical scenario for learning · Not a specific company endorsement"

# Original teaching snippets — common patterns expressed in our own examples.
CODE_SNIPPETS: dict[str, dict[str, str]] = {
    "gitops": {
        "title": "GitOps Application (declarative sync)",
        "lang": "yaml",
        "body": """# Declarative app — cluster reconciles to Git
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payments-api
  namespace: argocd
spec:
  project: production
  source:
    repoURL: https://github.com/org/platform-gitops
    path: apps/payments/overlays/prod
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: payments
  syncPolicy:
    automated:
      prune: true
      selfHeal: true""",
    },
    "kubernetes": {
        "title": "Deployment manifest (desired state)",
        "lang": "yaml",
        "body": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  labels:
    app: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: gateway
          image: registry.example/api:1.4.2
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi""",
    },
    "terraform": {
        "title": "Infrastructure as code (Terraform)",
        "lang": "hcl",
        "body": """terraform {
  required_version = ">= 1.6.0"
}

resource "azurerm_kubernetes_cluster" "platform" {
  name                = "aks-platform-prod"
  location            = var.region
  resource_group_name = azurerm_resource_group.core.name
  dns_prefix          = "platform-prod"

  default_node_pool {
    name       = "system"
    node_count = 3
    vm_size    = "Standard_D4s_v5"
  }
}""",
    },
    "jenkins": {
        "title": "Pipeline-as-code (declarative pattern)",
        "lang": "groovy",
        "body": """pipeline {
  agent any
  stages {
    stage('Build') {
      steps {
        sh 'make build'
        archiveArtifacts 'dist/**'
      }
    }
    stage('Test') {
      steps {
        sh 'make test'
      }
    }
    stage('Deploy') {
      when { branch 'main' }
      steps {
        sh 'make deploy staging'
      }
    }
  }
  post {
    failure {
      echo 'Notify platform team'
    }
  }
}""",
    },
    "incident": {
        "title": "Runbook step (automated remediation)",
        "lang": "yaml",
        "body": """# Playbook: rollback-on-error-spike
name: rollback-deploy-error-spike
trigger:
  metric: http_errors_5xx_rate
  threshold: "> 2%"
  window: 5m
  correlate_with: deploy_event
actions:
  - type: rollback
    target: last_known_good_release
  - type: verify
    checks:
      - health_endpoint: /healthz
      - metric: http_errors_5xx_rate
        expect: "< 0.5%"
notify:
  channel: "#incidents"
  include_timeline: true""",
    },
    "observability": {
        "title": "SLO definition (error budget)",
        "lang": "yaml",
        "body": """# Service level objective — 30-day window
service: checkout-api
objectives:
  - name: availability
    target: 99.9
    indicator:
      good: http_requests{status!~"5.."}
      total: http_requests
  - name: latency_p99
    target_ms: 400
    indicator:
      query: histogram_quantile(0.99, rate(http_duration_bucket[5m]))""",
    },
    "security": {
        "title": "Policy-as-code (admission check)",
        "lang": "yaml",
        "body": """# Deny containers running as root
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-non-root
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-run-as-non-root
      match:
        resources:
          kinds: [Pod]
      validate:
        message: "Containers must set runAsNonRoot=true"
        pattern:
          spec:
            containers:
              - securityContext:
                  runAsNonRoot: true""",
    },
    "docker": {
        "title": "Multi-stage Dockerfile (smaller images)",
        "lang": "dockerfile",
        "body": """FROM golang:1.22 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /bin/app ./cmd/api

FROM gcr.io/distroless/static-debian12
COPY --from=build /bin/app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]""",
    },
    "ansible": {
        "title": "Idempotent task (configuration drift fix)",
        "lang": "yaml",
        "body": """- name: Ensure nginx site config matches template
  template:
    src: site.conf.j2
    dest: /etc/nginx/sites-enabled/app.conf
    owner: root
    group: root
    mode: "0644"
  notify: reload nginx

- name: Ensure nginx is running
  service:
    name: nginx
    state: started
    enabled: true""",
    },
    "default": {
        "title": "Platform workflow (reference pattern)",
        "lang": "bash",
        "body": """#!/usr/bin/env bash
set -euo pipefail

# Build → test → scan → deploy (repeatable pipeline)
make lint test
trivy fs --severity HIGH,CRITICAL .
kubectl diff -f manifests/ || true
kubectl apply -f manifests/ --server-side
kubectl rollout status deploy/api-gateway -n prod --timeout=5m""",
    },
}

TOPIC_KEYWORDS: list[tuple[str, str]] = [
    ("gitops", "gitops"),
    ("argocd", "gitops"),
    ("flux", "gitops"),
    ("kubernetes", "kubernetes"),
    ("k8s", "kubernetes"),
    ("terraform", "terraform"),
    ("jenkins", "jenkins"),
    ("incident", "incident"),
    ("remediation", "incident"),
    ("sre", "incident"),
    ("observability", "observability"),
    ("slo", "observability"),
    ("prometheus", "observability"),
    ("security", "security"),
    ("devsecops", "security"),
    ("docker", "docker"),
    ("container", "docker"),
    ("ansible", "ansible"),
]

REFERENCE_LINKS: dict[str, list[str]] = {
    "gitops": [
        "OpenGitOps principles: opengitops.dev",
        "Kubernetes docs: kubernetes.io/docs",
    ],
    "kubernetes": [
        "Workloads: kubernetes.io/docs/concepts/workloads",
        "kubectl cheat sheet: kubernetes.io/docs/reference/kubectl",
    ],
    "terraform": [
        "Terraform language: developer.hashicorp.com/terraform/language",
        "Best practices: developer.hashicorp.com/terraform/cloud-docs/recommended-practices",
    ],
    "jenkins": [
        "Pipeline syntax: jenkins.io/doc/book/pipeline/syntax",
    ],
    "incident": [
        "Google SRE workbook: sre.google/workbook/incident-response",
    ],
    "observability": [
        "OpenTelemetry: opentelemetry.io/docs",
        "Prometheus docs: prometheus.io/docs",
    ],
    "security": [
        "CIS benchmarks: cisecurity.org",
        "NIST CSF: nist.gov/cyberframework",
    ],
    "default": [
        "CNCF landscape: landscape.cncf.io",
        "The Twelve-Factor App: 12factor.net",
    ],
}

ACTION_PREFIX = re.compile(
    r"^(first|second|third|fourth|fifth|one|two|three|four|here's what|step \d)",
    re.I,
)
NUMBERED_ITEM = re.compile(r"^\d+\.\s+")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def detect_topic_key(title: str, visual: str, voiceover: str, tags: str = "") -> str:
    combined = f"{title} {visual} {voiceover} {tags}".lower()
    for keyword, key in TOPIC_KEYWORDS:
        if keyword in combined:
            return key
    return "default"


def pick_code_snippet(title: str, visual: str, voiceover: str, tags: str = "") -> dict[str, str]:
    key = detect_topic_key(title, visual, voiceover, tags)
    return CODE_SNIPPETS.get(key, CODE_SNIPPETS["default"])


def pick_reference_links(title: str, visual: str, voiceover: str, tags: str = "") -> list[str]:
    key = detect_topic_key(title, visual, voiceover, tags)
    return REFERENCE_LINKS.get(key, REFERENCE_LINKS["default"])


def extract_takeaways(voiceover: str, limit: int = 4) -> list[str]:
    """Pull actionable sentences from narration for on-screen bullets."""
    if not voiceover:
        return []

    sentences = [s.strip() for s in SENTENCE_SPLIT.split(voiceover) if len(s.strip()) > 20]
    scored: list[tuple[int, str]] = []

    action_words = (
        "use", "start", "deploy", "audit", "measure", "migrate", "avoid", "ensure",
        "define", "implement", "monitor", "rollback", "commit", "sync", "verify",
        "never", "always", "key", "first", "critical", "important", "recommend",
    )

    for sentence in sentences:
        lower = sentence.lower()
        score = 0
        if any(word in lower for word in action_words):
            score += 2
        if NUMBERED_ITEM.match(sentence) or ACTION_PREFIX.match(lower):
            score += 3
        if re.search(r"\d+%|\d+x|\d+ hours|\d+ minutes", lower):
            score += 1
        if len(sentence) > 180:
            score -= 1
        scored.append((score, sentence))

    scored.sort(key=lambda item: item[0], reverse=True)
    takeaways: list[str] = []
    seen: set[str] = set()

    for _, sentence in scored:
        cleaned = NUMBERED_ITEM.sub("", sentence).strip()
        cleaned = re.sub(r"^(First|Second|Third|Fourth|One|Two|Three),?\s*", "", cleaned, flags=re.I)
        if len(cleaned) < 25:
            continue
        key = cleaned[:60].lower()
        if key in seen:
            continue
        seen.add(key)
        takeaways.append(cleaned[:140])
        if len(takeaways) >= limit:
            break

    if len(takeaways) < 2:
        for sentence in sentences[:limit]:
            cleaned = sentence[:140]
            if cleaned not in takeaways:
                takeaways.append(cleaned)
            if len(takeaways) >= limit:
                break

    return takeaways[:limit]


def extract_key_terms(visual: str, limit: int = 5) -> list[str]:
    """Extract labeled concepts from Visual: line for diagram labels."""
    items = parse_list_items_from_visual(visual)
    if items:
        return items[:limit]

    nodes = []
    if "→" in visual or "->" in visual:
        for part in re.split(r"\s*(?:→|->|—>)\s*", visual):
            part = re.sub(r"^(visual:|diagram:)\s*", "", part, flags=re.I).strip()
            part = part.split(".")[0].strip()
            if 3 < len(part) < 60:
                nodes.append(part)
    return nodes[:limit]


def parse_list_items_from_visual(visual: str) -> list[str]:
    items: list[str] = []
    for chunk in re.split(r"[.;]\s+", visual):
        chunk = chunk.strip()
        if not chunk or chunk.lower().startswith("visual:"):
            continue
        chunk = re.sub(r"^\d+\.\s*", "", chunk)
        if len(chunk) > 4:
            items.append(chunk)
    if len(items) == 1 and "," in items[0]:
        return [p.strip() for p in items[0].split(",") if len(p.strip()) > 3][:6]
    return items[:6]


def wants_code_slide(visual: str, title: str) -> bool:
    combined = f"{visual} {title}".lower()
    return any(
        term in combined
        for term in [
            "yaml", "manifest", "terraform", "hcl", "jenkinsfile", "pipeline config",
            "repository structure", "config", "code", "policy", "dockerfile", "runbook",
            "playbook library", "example",
        ]
    )


def chart_needs_disclaimer(visual: str, voiceover: str) -> bool:
    text = f"{visual} {voiceover}".lower()
    return any(
        phrase in text
        for phrase in [
            "report", "survey", "market share", "according to", "benchmark",
            "case study", "company", "2020", "2026", "adoption",
        ]
    )


def build_segment_context(segment: dict[str, Any], episode_title: str, tags: str = "") -> dict[str, Any]:
    """Enrich segment with original supporting content for rendering."""
    visual = segment.get("visual", "")
    voiceover = segment.get("voiceover", "")
    title = segment.get("title", "")

    return {
        "takeaways": extract_takeaways(voiceover),
        "code_snippet": pick_code_snippet(title, visual, voiceover, tags),
        "references": pick_reference_links(title, visual, voiceover, tags),
        "topic_key": detect_topic_key(title, visual, voiceover, tags),
        "show_chart_disclaimer": chart_needs_disclaimer(visual, voiceover),
        "show_case_study_note": "case study" in visual.lower() or "company" in voiceover.lower(),
    }
