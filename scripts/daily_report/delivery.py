"""Delivery-body preparation kept separate from SMTP transport."""

from __future__ import annotations

from dataclasses import dataclass

from .rendering import markdown_to_email_html, markdown_to_plain_text


@dataclass(frozen=True)
class DeliveryBodies:
    plain_text: str
    html_text: str


def build_delivery_bodies(markdown_report: str, *, title: str) -> DeliveryBodies:
    return DeliveryBodies(
        plain_text=markdown_to_plain_text(markdown_report),
        html_text=markdown_to_email_html(markdown_report, title=title),
    )
