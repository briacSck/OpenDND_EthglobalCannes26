"""Artifact Renderer — transforms quest briefs into real files (PDF, audio, HTML).

Handles both pre-quest bundle generation and live artifact rendering during gameplay.
"""

from __future__ import annotations

import os
import textwrap
from datetime import datetime

from agents.quest_generation.models import (
    QuestOutput, Character, EmailBundle, VoicemailBundle, PdfBundle, PlaylistBundle,
)
from agents.quest_runtime.models import Artifact


class ArtifactRenderer:
    """Generates real artifact files from quest data."""

    def __init__(self, output_dir: str = "artifacts"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _path(self, filename: str) -> str:
        return os.path.join(self.output_dir, filename)

    # ── Pre-quest bundle ─────────────────────────────────────────

    async def render_pre_quest_bundle(self, quest: QuestOutput) -> dict[str, str]:
        """Render all pre-quest artifacts. Returns {name: filepath}."""
        results = {}
        bundle = quest.pre_quest_bundle

        if bundle.email and bundle.email.body:
            path = self.render_email_pdf(bundle.email, quest.title)
            results["email"] = path

        if bundle.voicemail and bundle.voicemail.script:
            char = self._find_character(quest, bundle.voicemail.from_character)
            path = await self.render_voicemail(bundle.voicemail, char)
            results["voicemail"] = path

        if bundle.pdf and bundle.pdf.content_brief:
            path = self.render_classified_pdf(bundle.pdf, quest.title)
            results["classified_doc"] = path

        if bundle.playlist and bundle.playlist.name:
            path = self.render_playlist_html(bundle.playlist)
            results["playlist"] = path

        return results

    # ── Mission Briefing PDF ─────────────────────────────────────

    def render_briefing_pdf(self, quest: QuestOutput) -> str:
        """Render a minimal briefing: hook, situation, your role. Drops into vault after first contact."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas

        path = self._path("briefing.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        w, h = A4
        nu = quest.narrative_universe

        def _new_page():
            c.setFillColor(HexColor("#0d0d1a"))
            c.rect(0, 0, w, h, fill=1, stroke=0)
            c.setFillColor(HexColor("#00d4ff"))
            c.rect(0, h - 0.4 * cm, w, 0.4 * cm, fill=1, stroke=0)

        _new_page()

        # ── Title ──
        y = h - 2.5 * cm
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(HexColor("#00d4ff"))
        c.drawString(2.5 * cm, y, quest.title.upper())

        # ── Hook ──
        y -= 1.8 * cm
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(HexColor("#ff4444"))
        c.drawString(2.5 * cm, y, "INCOMING TRANSMISSION")
        y -= 0.7 * cm
        c.setFont("Courier", 9)
        c.setFillColor(HexColor("#cccccc"))
        for line in textwrap.wrap(nu.hook, width=80):
            if y < 2 * cm:
                c.showPage()
                _new_page()
                y = h - 2 * cm
                c.setFont("Courier", 9)
                c.setFillColor(HexColor("#cccccc"))
            c.drawString(2.5 * cm, y, line)
            y -= 0.4 * cm

        # ── Situation ──
        y -= 1 * cm
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(HexColor("#00d4ff"))
        c.drawString(2.5 * cm, y, "SITUATION")
        y -= 0.7 * cm
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#bbbbbb"))
        for line in textwrap.wrap(nu.context, width=85):
            if y < 2 * cm:
                c.showPage()
                _new_page()
                y = h - 2 * cm
                c.setFont("Helvetica", 9)
                c.setFillColor(HexColor("#bbbbbb"))
            c.drawString(2.5 * cm, y, line)
            y -= 0.4 * cm

        # ── Your role ──
        if nu.protagonist:
            y -= 1 * cm
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(HexColor("#00d4ff"))
            c.drawString(2.5 * cm, y, "YOUR ROLE")
            y -= 0.7 * cm
            c.setFont("Helvetica", 9)
            c.setFillColor(HexColor("#bbbbbb"))
            for line in textwrap.wrap(nu.protagonist, width=85):
                if y < 2 * cm:
                    c.showPage()
                    _new_page()
                    y = h - 2 * cm
                    c.setFont("Helvetica", 9)
                    c.setFillColor(HexColor("#bbbbbb"))
                c.drawString(2.5 * cm, y, line)
                y -= 0.4 * cm

        c.save()
        return path

    # ── Live artifact (from orchestrator) ────────────────────────

    async def render_artifact(self, artifact: Artifact, quest: QuestOutput) -> str | None:
        """Render a live artifact triggered by the orchestrator. Returns filepath."""

        if artifact.type == "classified_document":
            pdf = PdfBundle(type="classified_document", content_brief=artifact.description)
            return self.render_classified_pdf(pdf, quest.title, suffix=f"_{_ts()}")

        elif artifact.type == "intercepted_audio":
            # Try to find the character for voice
            char = self._find_character(quest, "")  # fallback
            vm = VoicemailBundle(from_character="Intercepted", script=artifact.description)
            return await self.render_voicemail(vm, char, suffix=f"_{_ts()}")

        elif artifact.type in ("coded_message", "handwritten_note"):
            return self.render_coded_message(artifact.description, suffix=f"_{_ts()}")

        elif artifact.type == "map":
            return self.render_coded_message(
                f"[MAP]\n\n{artifact.description}", suffix=f"_map_{_ts()}"
            )

        # Fallback: save as text
        path = self._path(f"artifact_{_ts()}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[{artifact.type}]\n\n{artifact.description}")
        return path

    # ── Email PDF ────────────────────────────────────────────────

    def render_email_pdf(self, email: EmailBundle, quest_title: str, suffix: str = "") -> str:
        """Render an email as a styled PDF with CONFIDENTIAL watermark."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor, red
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
        from reportlab.lib.enums import TA_LEFT

        path = self._path(f"email{suffix}.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        w, h = A4

        # Watermark
        c.saveState()
        c.setFont("Helvetica-Bold", 60)
        c.setFillColor(HexColor("#FFCCCC"))
        c.translate(w / 2, h / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, "CONFIDENTIAL")
        c.restoreState()

        # Header area
        y = h - 2 * cm
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(HexColor("#333333"))
        c.drawString(2 * cm, y, f"From:  {email.from_character}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"To:    [PLAYER]")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Subject:  {email.subject}")
        y -= 0.6 * cm
        c.drawString(2 * cm, y, f"Date:  {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC")
        y -= 0.4 * cm

        # Separator
        c.setStrokeColor(HexColor("#CC0000"))
        c.setLineWidth(2)
        c.line(2 * cm, y, w - 2 * cm, y)
        y -= 1 * cm

        # Body
        c.setFont("Courier", 9)
        c.setFillColor(HexColor("#111111"))
        lines = []
        for paragraph in email.body.split("\n"):
            lines.extend(textwrap.wrap(paragraph, width=80) or [""])

        for line in lines:
            if y < 2 * cm:
                c.showPage()
                y = h - 2 * cm
            c.drawString(2 * cm, y, line)
            y -= 0.4 * cm

        # Footer
        y -= 1 * cm
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(HexColor("#999999"))
        c.drawString(2 * cm, y, f"Quest: {quest_title} — This document is auto-generated and classified.")

        c.save()
        return path

    # ── Classified document PDF ──────────────────────────────────

    def render_classified_pdf(self, pdf: PdfBundle, quest_title: str, suffix: str = "") -> str:
        """Render a classified document with redacted style, stamps, margin notes."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor, black, white
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas

        path = self._path(f"classified{suffix}.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        w, h = A4

        # Dark header band
        c.setFillColor(HexColor("#1a1a2e"))
        c.rect(0, h - 3 * cm, w, 3 * cm, fill=1, stroke=0)

        # Title in header
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(white)
        c.drawString(2 * cm, h - 1.5 * cm, "CLASSIFIED — FORENSIC ANALYSIS")
        c.setFont("Helvetica", 9)
        c.drawString(2 * cm, h - 2.2 * cm, f"Re: {pdf.type}")
        c.drawString(2 * cm, h - 2.7 * cm, f"Date: {datetime.now().strftime('%Y-%m-%d')} | Status: DRAFT — NOT FOR DISTRIBUTION")

        # Red stamp
        c.saveState()
        c.setFont("Helvetica-Bold", 36)
        c.setFillColor(HexColor("#CC000044"))
        c.translate(w - 5 * cm, h - 6 * cm)
        c.rotate(-15)
        c.drawCentredString(0, 0, "DRAFT")
        c.restoreState()

        # Body
        y = h - 4.5 * cm
        c.setFont("Courier", 8.5)
        c.setFillColor(HexColor("#222222"))

        content = pdf.content_brief
        lines = []
        for paragraph in content.split("\n"):
            lines.extend(textwrap.wrap(paragraph, width=85) or [""])

        redact_keywords = ["redacted", "classified", "sealed"]

        for line in lines:
            if y < 2 * cm:
                c.showPage()
                y = h - 2 * cm

            # Simulate redaction bars on certain keywords
            lower = line.lower()
            has_redaction = any(kw in lower for kw in redact_keywords)

            c.drawString(2 * cm, y, line)

            if has_redaction:
                # Draw black bar over part of the line
                c.setFillColor(black)
                c.rect(8 * cm, y - 0.05 * cm, 5 * cm, 0.35 * cm, fill=1, stroke=0)
                c.setFillColor(HexColor("#222222"))

            y -= 0.4 * cm

        # Margin annotation
        y -= 1 * cm
        c.saveState()
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(HexColor("#CC3333"))
        c.rotate(2)
        note = "⚠ Voss cleared from Forensic Div. 2024. Who authorized this report?"
        c.drawString(2.5 * cm, y, note)
        c.restoreState()

        # Footer
        c.setFont("Helvetica", 6)
        c.setFillColor(HexColor("#666666"))
        c.drawString(2 * cm, 1 * cm, f"Quest: {quest_title} | Auto-generated classified document")

        c.save()
        return path

    # ── Voicemail audio (ElevenLabs) ─────────────────────────────

    async def render_voicemail(
        self, voicemail: VoicemailBundle, character: Character | None, suffix: str = ""
    ) -> str:
        """Render a voicemail as .mp3 using the character's ElevenLabs voice."""
        voice_id = character.voice_id if character else None

        if not voice_id or voice_id == "elevenlabs_placeholder" or not os.getenv("ELEVENLABS_API_KEY"):
            # Fallback: save script as text
            path = self._path(f"voicemail{suffix}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"[Voicemail from {voicemail.from_character}]\n\n{voicemail.script}")
            return path

        from agents.voice.tts import ElevenLabsTTS
        tts = ElevenLabsTTS(voice_id=voice_id)
        audio = await tts.synthesize(voicemail.script)

        path = self._path(f"voicemail{suffix}.mp3")
        with open(path, "wb") as f:
            f.write(audio)
        return path

    # ── Intercepted audio ────────────────────────────────────────

    async def render_intercepted_audio(
        self, script: str, characters: list[Character], suffix: str = ""
    ) -> str:
        """Render an intercepted conversation between characters as concatenated audio."""
        if not os.getenv("ELEVENLABS_API_KEY"):
            path = self._path(f"intercepted{suffix}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"[Intercepted Audio]\n\n{script}")
            return path

        from agents.voice.tts import ElevenLabsTTS

        # Parse lines like "[CharName] dialogue..."
        audio_chunks = []
        for line in script.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Try to match [CharName] pattern
            char = characters[0] if characters else None
            text = line
            if line.startswith("[") and "]" in line:
                name_end = line.index("]")
                name = line[1:name_end]
                text = line[name_end + 1:].strip()
                for c in characters:
                    if name.lower() in c.name.lower():
                        char = c
                        break

            voice_id = char.voice_id if char and char.voice_id != "elevenlabs_placeholder" else None
            if voice_id and text:
                tts = ElevenLabsTTS(voice_id=voice_id)
                chunk = await tts.synthesize(text)
                audio_chunks.append(chunk)

        path = self._path(f"intercepted{suffix}.mp3")
        with open(path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
        return path

    # ── Coded message / handwritten note ─────────────────────────

    def render_coded_message(self, text: str, suffix: str = "") -> str:
        """Render a coded message as a styled PDF."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas

        path = self._path(f"message{suffix}.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        w, h = A4

        # Aged paper look
        c.setFillColor(HexColor("#f5f0e1"))
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # Coffee stain circle (decorative)
        c.setFillColor(HexColor("#d4c5a0"))
        c.circle(w - 4 * cm, h - 4 * cm, 1.5 * cm, fill=1, stroke=0)
        c.setFillColor(HexColor("#f5f0e1"))
        c.circle(w - 4 * cm, h - 4 * cm, 1.1 * cm, fill=1, stroke=0)

        # Text
        y = h - 3 * cm
        c.setFont("Courier-Bold", 10)
        c.setFillColor(HexColor("#2a2a2a"))

        lines = []
        for paragraph in text.split("\n"):
            lines.extend(textwrap.wrap(paragraph, width=70) or [""])

        for line in lines:
            if y < 2 * cm:
                c.showPage()
                c.setFillColor(HexColor("#f5f0e1"))
                c.rect(0, 0, w, h, fill=1, stroke=0)
                y = h - 2 * cm
                c.setFont("Courier-Bold", 10)
                c.setFillColor(HexColor("#2a2a2a"))
            c.drawString(3 * cm, y, line)
            y -= 0.5 * cm

        c.save()
        return path

    # ── Playlist HTML ────────────────────────────────────────────

    def render_playlist_html(self, playlist: PlaylistBundle) -> str:
        """Render a playlist as a styled HTML file with Spotify search links."""
        keywords = playlist.genre_keywords or []
        links_html = "\n".join(
            f'<li><a href="https://open.spotify.com/search/{kw.replace(" ", "%20")}" target="_blank">{kw}</a></li>'
            for kw in keywords
        )

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{playlist.name}</title>
<style>
  body {{ background: #0d0d0d; color: #e0e0e0; font-family: 'Courier New', monospace;
         display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
  .card {{ background: #1a1a2e; border: 1px solid #333; border-radius: 12px;
           padding: 40px; max-width: 500px; box-shadow: 0 0 40px rgba(0,200,255,0.1); }}
  h1 {{ color: #00d4ff; font-size: 1.4em; margin-bottom: 5px; }}
  .mood {{ color: #888; font-style: italic; margin-bottom: 20px; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ margin: 8px 0; }}
  a {{ color: #1DB954; text-decoration: none; padding: 6px 12px;
       border: 1px solid #1DB954; border-radius: 20px; display: inline-block; }}
  a:hover {{ background: #1DB954; color: #000; }}
</style></head>
<body><div class="card">
  <h1>🎵 {playlist.name}</h1>
  <p class="mood">{playlist.mood}</p>
  <ul>{links_html}</ul>
</div></body></html>"""

        path = self._path("playlist.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path

    # ── Helpers ───────────────────────────────────────────────────

    def _find_character(self, quest: QuestOutput, name: str) -> Character | None:
        """Find a character by partial name match."""
        if not name:
            return quest.characters[0] if quest.characters else None
        lower = name.lower()
        for c in quest.characters:
            if lower in c.name.lower():
                return c
        return quest.characters[0] if quest.characters else None


def _ts() -> str:
    return datetime.now().strftime("%H%M%S")
