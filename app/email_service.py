from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pybars import Compiler

from app.settings import Settings


@dataclass
class RenderedEmail:
    subject: str
    html: str


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "email-templates"


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._compiler = Compiler()
        self._partials = self._load_partials()

    def _load_partials(self) -> dict[str, Any]:
        partials_dir = TEMPLATE_DIR / "partials"
        partials: dict[str, Any] = {}
        if not partials_dir.exists():
            return partials
        for path in partials_dir.glob("*.hbs"):
            partials[path.stem] = self._compiler.compile(path.read_text(encoding="utf-8"))
        return partials

    def _render(self, template_name: str, context: dict[str, Any]) -> str:
        template_path = TEMPLATE_DIR / f"{template_name}.hbs"
        layout_path = TEMPLATE_DIR / "layouts" / "base.hbs"
        body_template = self._compiler.compile(template_path.read_text(encoding="utf-8"))
        body = body_template(context, partials=self._partials)

        layout_template = self._compiler.compile(layout_path.read_text(encoding="utf-8"))
        return layout_template({"body": body}, partials=self._partials)

    def render_forgot_password(self, user_name: str, token: str) -> RenderedEmail:
        html = self._render("forgot-password", {"userName": user_name, "token": token})
        return RenderedEmail(subject="Reset your PharmacyOS password", html=html)

    async def send_reset_email(self, to_email: str, user_name: str, token: str) -> None:
        rendered = self.render_forgot_password(user_name, token)

        if self.settings.email_provider == "console":
            return

        if self.settings.email_provider != "resend":
            raise ValueError("Unsupported email provider")

        if not self.settings.resend_api_key or not self.settings.email_from:
            raise ValueError("Email provider not configured")

        payload = {
            "from": self.settings.email_from,
            "to": [to_email],
            "subject": rendered.subject,
            "html": rendered.html,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                json=payload,
            )
            response.raise_for_status()