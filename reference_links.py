"""Official documentation links per episode (text-only references in descriptions)."""

from __future__ import annotations

EPISODE_REFERENCES: dict[int, list[tuple[str, str]]] = {
    1: [
        ("Jenkins documentation", "https://www.jenkins.io/doc/"),
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
    16: [
        ("Google SRE books (free)", "https://sre.google/books/"),
        ("Site Reliability Engineering overview", "https://sre.google/sre-book/table-of-contents/"),
    ],
}


def references_for_video(video_number: int) -> list[tuple[str, str]]:
    return EPISODE_REFERENCES.get(video_number, [])
