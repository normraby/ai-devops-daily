"""Official documentation links per episode (text-only references in descriptions)."""

from __future__ import annotations

EPISODE_REFERENCES: dict[int, list[tuple[str, str]]] = {
    1: [
        ("Jenkins documentation", "https://www.jenkins.io/doc/"),
        ("CNCF CI/CD landscape", "https://landscape.cncf.io/"),
    ],
    2: [
        ("Terraform documentation", "https://developer.hashicorp.com/terraform/docs"),
        ("Jenkins documentation", "https://www.jenkins.io/doc/"),
    ],
    3: [
        ("Jenkins Pipeline documentation", "https://www.jenkins.io/doc/book/pipeline/"),
        ("CNCF CI/CD landscape", "https://landscape.cncf.io/"),
    ],
    4: [
        ("Kubernetes cost optimization (official docs)", "https://kubernetes.io/docs/concepts/cluster-administration/manage-deployment/"),
    ],
    5: [
        ("OpenGitOps principles", "https://opengitops.dev/"),
    ],
    6: [
        ("Kubernetes documentation", "https://kubernetes.io/docs/home/"),
    ],
    7: [
        ("OWASP Top Ten", "https://owasp.org/www-project-top-ten/"),
        ("CIS Benchmarks overview", "https://www.cisecurity.org/cis-benchmarks"),
    ],
    8: [
        ("Prometheus documentation", "https://prometheus.io/docs/introduction/overview/"),
    ],
    9: [
        ("OpenTelemetry documentation", "https://opentelemetry.io/docs/"),
    ],
    10: [
        ("Kubernetes documentation", "https://kubernetes.io/docs/home/"),
    ],
    11: [
        ("Argo CD documentation", "https://argo-cd.readthedocs.io/"),
    ],
    12: [
        ("Flux documentation", "https://fluxcd.io/flux/"),
    ],
    13: [
        ("Kubernetes documentation", "https://kubernetes.io/docs/home/"),
    ],
    14: [
        ("CNCF landscape", "https://landscape.cncf.io/"),
    ],
    15: [
        ("NIST Cybersecurity Framework", "https://www.nist.gov/cyberframework"),
    ],
    16: [
        ("Google SRE books (free)", "https://sre.google/books/"),
        ("Site Reliability Engineering overview", "https://sre.google/sre-book/table-of-contents/"),
    ],
}


def references_for_video(video_number: int) -> list[tuple[str, str]]:
    return EPISODE_REFERENCES.get(video_number, [])
