"""Canonical "About Karcytics" / "About the Developer" text.

Single source of truth for both the Hub's own in-process About dialogs
(`karcytics/ui/dialogs/about_karcytics.py`, `about_developer.py`) and the
`menu.get_about_karcytics`/`menu.get_about_developer` CoreServicesServer
handlers an isolated plugin's own Help menu calls (see
`core_services_bootstrap.py`) — so the two can't silently drift apart the
way two independently hand-maintained copies of the same paragraph would.
"""

from __future__ import annotations

from karcytics.core.config import AppConfig

KARCYTICS_ABOUT: dict[str, str] = {
    "name": "Karcytics™",
    "version": AppConfig.CORE_VERSION,
    "tagline": "Bio Analysis Made Simple",
    "description": (
        "A free, intuitive platform designed to streamline laboratory "
        "data analysis for students, researchers, and professionals."
    ),
    "copyright": (
        "© 2026 Karcytics Contributors. Free for academic & personal use under "
        "the PolyForm Noncommercial License 1.0.0."
    ),
}

DEVELOPER_ABOUT: dict[str, str] = {
    "name": "Kalaimaran Balasothy",
    "role": "Biomedical Engineering Student",
    "bio": (
        "Kalaimaran Balasothy is a Biomedical Engineering undergraduate at the "
        "University of British Columbia with a specialized focus on "
        "Bioinformatics and Cellular Engineering.\n\n"
        "Driven by a deep passion for immunoengineering and synthetic biology, "
        "he draws on his background in software automation to bridge the gap "
        "between computer science and wet-lab research.\n\n"
        "Combining his technical experience with a love for teaching, he builds "
        "accessible software that simplifies laboratory data analysis for "
        "scientists at every level."
    ),
}
