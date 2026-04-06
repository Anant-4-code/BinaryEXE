"""Generate an attractive, well-formatted prescription PDF with language support."""
import json
import os
import hashlib
import uuid
from pathlib import Path
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.models.models import Prescription
from app.services.translation_service import translate_prescription
from app.utils import format_frequency


def _infer_medicine_type(name: str) -> str:
    """Infer medicine type from name (Tablet, Syrup, Capsule, etc.)."""
    n = (name or "").lower()
    if "tab" in n or "tablet" in n or "dt" in n:
        return "Tablet"
    if "syp" in n or "syrup" in n or "susp" in n:
        return "Syrup"
    if "cap" in n or "capsule" in n:
        return "Capsule"
    if "inj" in n or "injection" in n:
        return "Injection"
    if "drop" in n:
        return "Drops"
    if "cream" in n or "gel" in n or "ointment" in n:
        return "Topical"
    return "Medicine"


def generate_prescription_pdf(
    db: Session,
    prescription_id: int,
    language: Optional[str] = None,
) -> bytes:
    """Generate a prescription PDF in a fixed layout similar to the provided sample.

    If `language` is provided and matches the stored `transliterated_json.language`, the PDF will use
    transliterated patient/doctor/medicines blocks; otherwise it will use the structured DB fields.
    """
    prescription = db.query(Prescription).get(prescription_id)
    if not prescription:
        raise ValueError("Prescription not found")

    lang_key = (language or "").lower().strip()

    transliterated = None
    if prescription.transliterated_json:
        try:
            t = json.loads(prescription.transliterated_json)
            if t.get("language") == lang_key:
                transliterated = t
        except (json.JSONDecodeError, TypeError):
            pass

    patient_details = {}
    doctor_details = {}
    if prescription.patient_details_json:
        try:
            patient_details = json.loads(prescription.patient_details_json)
        except (json.JSONDecodeError, TypeError):
            pass
    if prescription.doctor_details_json:
        try:
            doctor_details = json.loads(prescription.doctor_details_json)
        except (json.JSONDecodeError, TypeError):
            pass

    export_overrides = {}
    if getattr(prescription, "export_overrides_json", None):
        try:
            export_overrides = json.loads(prescription.export_overrides_json) or {}
        except (json.JSONDecodeError, TypeError):
            export_overrides = {}

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Try to use a Unicode-capable TTF font for the selected language (Windows fonts).
    # If unavailable, fall back to Helvetica (note: non-Latin scripts may render as boxes).
    def _try_register_font(font_name: str, font_path: str) -> Optional[str]:
        try:
            if not font_path or not os.path.exists(font_path):
                return None
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
        except Exception:
            return None

    def _select_body_font() -> str:
        project_fonts_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
        # A pragmatic mapping for common Indic scripts on Windows.
        win_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")

        broad_candidates = [
            ("BodyFont_NirmalaUI", os.path.join(win_fonts, "Nirmala.ttf")),
            ("BodyFont_SegoeUI", os.path.join(win_fonts, "segoeui.ttf")),
        ]
        mapping = {
            "hindi": os.path.join(win_fonts, "mangal.ttf"),
            "marathi": os.path.join(win_fonts, "mangal.ttf"),
            "sanskrit": os.path.join(win_fonts, "mangal.ttf"),
            "tamil": os.path.join(win_fonts, "latha.ttf"),
            "telugu": os.path.join(win_fonts, "gautami.ttf"),
            "kannada": os.path.join(win_fonts, "tunga.ttf"),
            "gujarati": os.path.join(win_fonts, "shruti.ttf"),
            "punjabi": os.path.join(win_fonts, "raavi.ttf"),
            "bengali": os.path.join(win_fonts, "vrinda.ttf"),
            "malayalam": os.path.join(win_fonts, "kartika.ttf"),
            "odia": os.path.join(win_fonts, "kalinga.ttf"),
        }
        if not lang_key or lang_key == "english":
            if project_fonts_dir.exists() and project_fonts_dir.is_dir():
                try:
                    for p in sorted([p for p in project_fonts_dir.glob("*.ttf") if p.is_file()]):
                        reg = _try_register_font(f"BodyFont_Project_{p.stem}", str(p))
                        if reg:
                            return reg
                except Exception:
                    pass
            return "Helvetica"

        # Order matters (to avoid missing glyphs / square boxes):
        # 1) project language-specific fonts
        if project_fonts_dir.exists() and project_fonts_dir.is_dir():
            try:
                ttf_files = sorted([p for p in project_fonts_dir.glob("*.ttf") if p.is_file()])
                lang_hits = [
                    p
                    for p in ttf_files
                    if lang_key in p.stem.lower() or lang_key.replace("_", "") in p.stem.lower()
                ]
                for p in lang_hits:
                    reg = _try_register_font(f"BodyFont_Project_{p.stem}", str(p))
                    if reg:
                        return reg
            except Exception:
                pass

        # 2) windows language-specific fonts
        path = mapping.get(lang_key)
        reg = _try_register_font(f"BodyFont_{lang_key}", path) if path else None
        if reg:
            return reg

        for fname, fpath in broad_candidates:
            reg = _try_register_font(fname, fpath)
            if reg:
                return reg

        # 3) last fallback: any project font (may or may not include the script)
        if project_fonts_dir.exists() and project_fonts_dir.is_dir():
            try:
                for p in sorted([p for p in project_fonts_dir.glob("*.ttf") if p.is_file()]):
                    reg = _try_register_font(f"BodyFont_Project_{p.stem}", str(p))
                    if reg:
                        return reg
            except Exception:
                pass

        return "Helvetica"

    body_font = _select_body_font()

    # If user requested a non-English language but we don't have stored transliteration,
    # translate on-demand (uses translation_service).
    if lang_key and lang_key != "english" and not transliterated:
        def _dict_to_section(dct: dict) -> str:
            lines = []
            for k, v in (dct or {}).items():
                if v and str(v).strip():
                    lines.append(f"{str(k).replace('_', ' ').title()}: {v}")
            return "\n".join(lines)

        p_text = export_overrides.get("patient_text") or _dict_to_section(patient_details)
        d_text = export_overrides.get("doctor_text") or _dict_to_section(doctor_details)
        m_lines = []
        for i, m in enumerate(prescription.medicines or [], 1):
            name = m.normalized_name or m.original_name or f"Medicine {i}"
            dose = m.dose or "—"
            freq = format_frequency(m.frequency)
            dur = f"{m.duration_days} days" if m.duration_days else "—"
            inst = (m.instructions or "").strip()
            expl = (m.explanation or "").strip()
            m_lines.append(f"{i}. {name}\nDose: {dose} | Frequency: {freq} | Duration: {dur}\n{inst}\n{expl}".strip())
        meds_text = "\n\n".join([x for x in m_lines if x])

        try:
            translated = translate_prescription(p_text, d_text, meds_text, lang_key)
            transliterated = {
                "language": lang_key,
                "label": lang_key.title(),
                "patient": translated.get("patient", ""),
                "doctor": translated.get("doctor", ""),
                "medicines": translated.get("medicines", ""),
                "full": translated.get("full", ""),
            }
        except Exception:
            transliterated = None

    page_margin_x = 0.55 * inch
    top_y = height - 0.6 * inch
    content_w = width - 2 * page_margin_x

    # Teal palette (medical)
    primary = colors.HexColor("#1ABC9C")
    dark_accent = colors.HexColor("#17A589")
    soft_accent = colors.HexColor("#48C9B0")
    tint = colors.HexColor("#D1F2EB")

    bg = colors.white
    border = colors.HexColor("#d1d5db")
    header_text = colors.HexColor("#111827")
    table_header_bg = primary
    muted = colors.HexColor("#6b7280")
    light_row = colors.HexColor("#f9fafb")

    def wrap_lines(text: str, font_name: str, font_size: int, max_width: float):
        if not text:
            return []
        out = []
        for raw in str(text).split("\n"):
            line = raw.strip()
            if not line:
                continue
            while pdf.stringWidth(line, font_name, font_size) > max_width and len(line) > 1:
                cut = len(line)
                while cut > 1 and pdf.stringWidth(line[:cut], font_name, font_size) > max_width:
                    cut -= 1
                out.append(line[:cut].rstrip())
                line = line[cut:].lstrip()
            if line:
                out.append(line)
        return out

    page_no = 1
    content_top_y = top_y - 1.45 * inch

    def _prescription_uuid() -> str:
        seed = f"prescription:{prescription.id}:{prescription.user_id}:{prescription.created_at.isoformat() if prescription.created_at else ''}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

    def _verification_hash_short() -> str:
        seed = f"{prescription.id}|{prescription.user_id}|{prescription.created_at.isoformat() if prescription.created_at else ''}|{prescription.title}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

    def draw_footer():
        pdf.setStrokeColor(border)
        pdf.setLineWidth(0.8)
        pdf.line(page_margin_x, 0.65 * inch, width - page_margin_x, 0.65 * inch)

        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(muted)
        pdf.drawString(page_margin_x, 0.48 * inch, "Generated by Sanjeevani AI • Not a substitute for medical judgment")
        pdf.drawString(page_margin_x, 0.33 * inch, "Emergency Disclaimer: If symptoms worsen, seek immediate medical help • Privacy: Data handled per policy")
        pdf.setFont("Helvetica", 7)
        pdf.drawString(page_margin_x, 0.20 * inch, f"Font: {body_font} | Lang: {lang_key or 'english'}")
        pdf.drawRightString(width - page_margin_x, 0.45 * inch, f"Page {page_no}")

    def new_page():
        nonlocal page_no
        draw_footer()
        pdf.showPage()
        page_no += 1
        draw_page_bg()
        draw_header()

    def ensure_space(y: float, needed: float) -> float:
        # Keep a comfortable gap above footer to avoid visual collisions.
        if y - needed < 1.35 * inch:
            new_page()
            return content_top_y
        return y

    def draw_page_bg():
        pdf.setFillColor(bg)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)

        # subtle page border
        pdf.setStrokeColor(border)
        pdf.setLineWidth(1)
        pdf.rect(0.35 * inch, 0.35 * inch, width - 0.70 * inch, height - 0.70 * inch, fill=0, stroke=1)

        # watermark
        pdf.saveState()
        pdf.setFillColor(colors.HexColor("#e5e7eb"))
        try:
            pdf.setFont("Helvetica-Bold", 80)
        except Exception:
            pdf.setFont("Helvetica", 80)
        pdf.translate(width / 2, height / 2)
        pdf.rotate(30)
        pdf.drawCentredString(0, 0, "RX")
        pdf.restoreState()

    def draw_header():
        nonlocal content_top_y
        y_top = height - 0.45 * inch

        # left: logo + platform
        logo_r = 0.20 * inch
        cx = page_margin_x + logo_r
        cy = y_top - 0.30 * inch
        pdf.setFillColor(tint)
        pdf.setStrokeColor(primary)
        pdf.circle(cx, cy, logo_r, fill=1, stroke=1)
        pdf.setFillColor(dark_accent)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(cx, cy - 4, "RX")

        pdf.setFillColor(header_text)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(page_margin_x + 0.50 * inch, y_top - 0.18 * inch, "Sanjeevani AI")
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(muted)
        pdf.drawString(
            page_margin_x + 0.50 * inch,
            y_top - 0.38 * inch,
            "AI-Assisted Prescription Interpretation System",
        )
        pdf.setFont("Helvetica-Oblique", 8)
        pdf.drawString(
            page_margin_x + 0.50 * inch,
            y_top - 0.55 * inch,
            "Digitally Generated & Clinically Validated",
        )

        # right: verification
        created = prescription.created_at
        issue_date = export_overrides.get("date") or (created.strftime("%d-%m-%Y") if created else "")
        gen_ts = export_overrides.get("time") or (created.strftime("%H:%M") if created else "")
        pid = _prescription_uuid()
        vhash = _verification_hash_short()

        right_x = width - page_margin_x
        right_col_w = content_w * 0.46
        right_col_left = right_x - right_col_w

        def draw_right_lines(lines: list[str], y_start: float, font_name: str, font_size: int, color) -> float:
            pdf.setFont(font_name, font_size)
            pdf.setFillColor(color)
            y_cur = y_start
            for ln in lines:
                for wln in wrap_lines(ln, font_name, font_size, right_col_w):
                    w = pdf.stringWidth(wln, font_name, font_size)
                    pdf.drawString(right_x - w, y_cur, wln)
                    y_cur -= 0.16 * inch
            return y_cur

        y_right = y_top - 0.15 * inch
        y_right = draw_right_lines([f"Prescription ID: {pid}"], y_right, "Helvetica", 7, header_text)
        y_right = draw_right_lines(
            [
                f"Issue Date: {issue_date}",
                f"Generated: {gen_ts}",
                "System Version: v1",
                f"Verification Hash: {vhash}",
            ],
            y_right - 0.02 * inch,
            "Helvetica",
            8,
            muted,
        )

        # Compute dynamic header height based on the lower of left vs right content
        left_bottom = y_top - 0.80 * inch
        right_bottom = y_right
        y_bottom = min(left_bottom, right_bottom, y_top - 1.05 * inch)

        # bottom border accent
        pdf.setStrokeColor(primary)
        pdf.setLineWidth(2)
        pdf.line(page_margin_x, y_bottom, width - page_margin_x, y_bottom)

        content_top_y = y_bottom - 0.25 * inch

    def draw_patient_doctor_cards(y: float) -> float:
        y = ensure_space(y, 2.35 * inch)
        box_h = 1.95 * inch
        gap = 0.2 * inch
        box_w = (content_w - gap) / 2
        x1 = page_margin_x
        x2 = page_margin_x + box_w + gap
        y_top = y
        y_bottom = y_top - box_h

        def draw_card(x: float, title: str):
            pdf.setStrokeColor(border)
            pdf.setFillColor(tint)
            pdf.rect(x, y_bottom, box_w, box_h, fill=1, stroke=1)
            pdf.setFillColor(dark_accent)
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(x + 0.15 * inch, y_top - 0.30 * inch, title)
            pdf.setStrokeColor(soft_accent)
            pdf.setLineWidth(1)
            pdf.line(x + 0.15 * inch, y_top - 0.36 * inch, x + box_w - 0.15 * inch, y_top - 0.36 * inch)

        draw_card(x1, "Patient Information")
        draw_card(x2, "Doctor Information")

        override_patient_text = (export_overrides.get("patient_text") or "").strip()
        override_doctor_text = (export_overrides.get("doctor_text") or "").strip()
        override_patient = export_overrides.get("patient") or {}
        override_doctor = export_overrides.get("doctor") or {}

        def draw_kv_list(x: float, data_lines: list[str]):
            pdf.setFillColor(header_text)
            pdf.setFont(body_font, 9)
            max_w = box_w - 0.30 * inch
            y_cur = y_top - 0.58 * inch
            for line in data_lines:
                for wline in wrap_lines(line, body_font, 9, max_w)[:2]:
                    pdf.drawString(x + 0.15 * inch, y_cur, wline[:140])
                    y_cur -= 0.20 * inch
                if y_cur < y_bottom + 0.20 * inch:
                    break

        if override_patient or override_doctor:
            def _dict_lines(dct: dict) -> list[str]:
                order = ["full_name", "age", "gender", "patient_id", "contact", "address", "allergies"]
                out = []
                for k in order:
                    if dct.get(k):
                        out.append(f"{k.replace('_',' ').title()}: {dct.get(k)}")
                for k, v in dct.items():
                    if k in order:
                        continue
                    if v and str(v).strip():
                        out.append(f"{str(k).replace('_',' ').title()}: {v}")
                return out

            p_lines = _dict_lines(override_patient)
            d_lines = _dict_lines(override_doctor)
        elif override_patient_text or override_doctor_text:
            p_lines = [ln.strip() for ln in override_patient_text.split("\n") if ln.strip()]
            d_lines = [ln.strip() for ln in override_doctor_text.split("\n") if ln.strip()]
        elif transliterated and (transliterated.get("patient") or transliterated.get("doctor")):
            p_lines = [ln.strip() for ln in (transliterated.get("patient") or "").split("\n") if ln.strip()]
            d_lines = [ln.strip() for ln in (transliterated.get("doctor") or "").split("\n") if ln.strip()]
        else:
            # prefer explicit clinical fields
            p_order = [
                "full_name",
                "name",
                "age",
                "gender",
                "patient_id",
                "contact",
                "phone",
                "address",
                "allergies",
            ]
            d_order = [
                "doctor_name",
                "name",
                "specialization",
                "registration_number",
                "license_number",
                "clinic",
                "hospital",
                "contact",
                "digital_signature_status",
            ]

            def pick_lines(dct: dict, order: list[str]) -> list[str]:
                out = []
                seen = set()
                for k in order:
                    if k in (dct or {}) and (dct.get(k) is not None) and str(dct.get(k)).strip():
                        out.append(f"{k.replace('_', ' ').title()}: {dct.get(k)}")
                        seen.add(k)
                for k, v in (dct or {}).items():
                    if k in seen:
                        continue
                    if v is None or not str(v).strip():
                        continue
                    out.append(f"{str(k).replace('_', ' ').title()}: {v}")
                return out

            p_lines = pick_lines(patient_details, p_order)
            d_lines = pick_lines(doctor_details, d_order)

        draw_kv_list(x1, p_lines)
        draw_kv_list(x2, d_lines)

        return y_bottom - 0.30 * inch

    def draw_adherence_summary(y: float) -> float:
        # Optional: only show when prescription is ACTIVE and doses exist
        if getattr(prescription, "status", "") != "active":
            return y
        doses = getattr(prescription, "doses", None) or []
        if not doses:
            return y

        dates = [d.date for d in doses if getattr(d, "date", None)]
        if not dates:
            return y
        start_date = min(dates)
        end_date = max(dates)
        total = len(doses)
        taken = len([d for d in doses if getattr(d, "taken", False)])

        lines = [
            f"Start Date: {start_date.strftime('%d-%m-%Y')}",
            f"End Date: {end_date.strftime('%d-%m-%Y')}",
            f"Total Doses: {total}",
            f"Taken Doses: {taken}",
        ]

        label_h = 0.30 * inch
        line_h = 0.22 * inch
        block_h = label_h + 0.25 * inch + (len(lines) * line_h) + 0.10 * inch
        y = ensure_space(y, block_h + 0.30 * inch)

        pdf.setStrokeColor(border)
        pdf.setFillColor(colors.white)
        pdf.rect(page_margin_x, y - block_h, content_w, block_h, fill=1, stroke=1)

        pdf.setFillColor(colors.HexColor("#f0fdfa"))
        pdf.rect(page_margin_x, y - 0.30 * inch, content_w, 0.30 * inch, fill=1, stroke=0)
        pdf.setFillColor(dark_accent)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(page_margin_x + 0.12 * inch, y - 0.22 * inch, "Adherence Schedule Summary")

        pdf.setFont(body_font, 9)
        pdf.setFillColor(header_text)
        y_cur = y - 0.55 * inch
        for ln in lines:
            pdf.drawString(page_margin_x + 0.12 * inch, y_cur, ln)
            y_cur -= 0.22 * inch

        return y - block_h - 0.30 * inch

    def draw_medicines_table(y: float) -> float:
        # Name, Formulation/Dose, Frequency, Duration, Instructions, Confidence
        # 6 columns => 7 boundaries.
        cols = [0.0, 0.25, 0.45, 0.58, 0.68, 0.92, 1.0]
        col_x = [page_margin_x + c * content_w for c in cols]
        row_h = 0.40 * inch

        headers = [
            "Medicine Name",
            "Formula / Dose",
            "Frequency",
            "Span (Days)",
            "Special Instructions",
            "Conf %",
        ]

        def draw_table_header(yh: float) -> float:
            pdf.setStrokeColor(border)
            pdf.setFillColor(table_header_bg)
            pdf.rect(page_margin_x, yh - row_h, content_w, row_h, fill=1, stroke=1)

            pdf.setFont("Helvetica-Bold", 8)
            pdf.setFillColor(colors.white)
            for i, h in enumerate(headers):
                cell_w = (col_x[i + 1] - col_x[i]) - 0.12 * inch
                label = h
                if i == 5 and cell_w < 1.7 * inch:
                    label = "Special Instr."
                if i == 6 and cell_w < 0.45 * inch:
                    label = "Conf"
                wlines = wrap_lines(label, "Helvetica-Bold", 8, max(0.10 * inch, cell_w))[:1]
                pdf.drawString(col_x[i] + 0.06 * inch, yh - 0.26 * inch, (wlines[0] if wlines else ""))

            pdf.setStrokeColor(border)
            for cx in col_x[1:-1]:
                pdf.line(cx, yh - row_h, cx, yh)

            return yh - row_h

        y = ensure_space(y, 1.1 * inch)
        y_cursor = draw_table_header(y)

        meds = prescription.medicines or []
        pdf.setFont(body_font, 9)

        if not meds:
            y_cursor = ensure_space(y_cursor, row_h + 0.25 * inch)
            pdf.setFillColor(colors.white)
            pdf.rect(page_margin_x, y_cursor - row_h, content_w, row_h, fill=1, stroke=1)
            pdf.setFillColor(muted)
            pdf.drawString(page_margin_x + 0.08 * inch, y_cursor - 0.24 * inch, "No medicines extracted. Run AI Extraction first.")
            return y_cursor - row_h - 0.35 * inch

        for idx, m in enumerate(meds, 1):
            y_cursor = ensure_space(y_cursor, row_h + 0.25 * inch)
            # If we just paginated, redraw table header.
            if abs(y_cursor - content_top_y) < 0.01:
                y_cursor = draw_table_header(y_cursor)

            pdf.setFillColor(light_row if idx % 2 == 0 else colors.white)
            pdf.rect(page_margin_x, y_cursor - row_h, content_w, row_h, fill=1, stroke=1)
            for cx in col_x[1:-1]:
                pdf.line(cx, y_cursor - row_h, cx, y_cursor)

            name = m.normalized_name or m.original_name or f"Medicine {idx}"
            dose = m.dose or "—"
            freq = format_frequency(m.frequency)
            dur = f"{m.duration_days} days" if m.duration_days else "—"
            inst = (m.instructions or "").strip() or "—"

            strength = "—"
            for src in [m.dose, m.original_name, m.normalized_name]:
                s = (src or "")
                if "mg" in s.lower() or "ml" in s.lower():
                    strength = s
                    break

            conf_val = m.confidence if m.confidence is not None else 0.0
            conf_pct = conf_val * 100.0 if conf_val <= 1.0 else conf_val
            conf_pct = max(0.0, min(100.0, float(conf_pct)))

            def conf_color(p: float):
                if p >= 80:
                    return colors.HexColor("#16a34a")
                if p >= 60:
                    return colors.HexColor("#f59e0b")
                return colors.HexColor("#dc2626")

            combined_dose = f"{strength} | {dose}" if strength != dose and strength != "—" else dose

            pdf.setFillColor(header_text)
            name_lines = wrap_lines(name, body_font, 9, (col_x[1] - col_x[0]) - 0.16 * inch)
            pdf.drawString(col_x[0] + 0.08 * inch, y_cursor - 0.24 * inch, (name_lines[0] if name_lines else "")[:50])
            pdf.drawString(col_x[1] + 0.08 * inch, y_cursor - 0.24 * inch, str(combined_dose)[:35])
            pdf.drawString(col_x[2] + 0.08 * inch, y_cursor - 0.24 * inch, str(freq)[:18])
            pdf.drawString(col_x[3] + 0.08 * inch, y_cursor - 0.24 * inch, str(dur)[:12])

            inst_lines = wrap_lines(inst, body_font, 8, (col_x[5] - col_x[4]) - 0.16 * inch)
            pdf.setFont(body_font, 8)
            pdf.drawString(col_x[4] + 0.08 * inch, y_cursor - 0.22 * inch, (inst_lines[0] if inst_lines else "—")[:80])
            pdf.setFont(body_font, 9)

            # confidence badge
            badge_w = (col_x[6] - col_x[5]) - 0.16 * inch
            bx = col_x[5] + 0.08 * inch
            by = y_cursor - 0.31 * inch
            pdf.setFillColor(conf_color(conf_pct))
            pdf.roundRect(bx, by, max(0.2 * inch, badge_w), 0.22 * inch, 4, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawCentredString(bx + max(0.2 * inch, badge_w) / 2, by + 0.06 * inch, f"{int(round(conf_pct))}%")
            pdf.setFont(body_font, 9)

            y_cursor -= row_h

        return y_cursor - 0.35 * inch

    def draw_patient_friendly_explanation(y: float) -> float:
        max_w = content_w - 0.36 * inch

        override_instructions = (export_overrides.get("instructions_text") or "").strip()
        if override_instructions:
            lines = wrap_lines(override_instructions, body_font, 9, max_w)
        elif transliterated and transliterated.get("medicines"):
            lines = wrap_lines(transliterated.get("medicines") or "", body_font, 9, max_w)
        else:
            items = []
            for i, m in enumerate(prescription.medicines or [], 1):
                name = m.normalized_name or m.original_name or f"Medicine {i}"
                inst = (m.instructions or "").strip()
                expl = (m.explanation or "").strip()
                parts = []
                dose = (m.dose or "").strip()
                freq = (format_frequency(m.frequency) or "").strip()
                dur = f"{m.duration_days} days" if (m.duration_days and m.duration_days > 0) else ""
                if dose:
                    parts.append(f"Dose: {dose}")
                if freq:
                    parts.append(f"Frequency: {freq}")
                if dur:
                    parts.append(f"Duration: {dur}")

                msg = inst
                if expl:
                    msg = (msg + " | " if msg else "") + expl
                if not msg:
                    msg = "; ".join(parts) if parts else "Take as directed by your doctor."

                msg = msg[:200]
                items.append(f"{i}. {name}: {msg}")
            lines = []
            for it in items:
                lines.extend(wrap_lines(it, body_font, 9, max_w))

        if not lines:
            lines = ["No explanation/instructions available."]

        # Paginate this block if it becomes long.
        per_page_box_h = 2.5 * inch
        label_h = 0.28 * inch
        line_h = 0.20 * inch
        usable_h = per_page_box_h - (0.55 * inch)
        max_lines = max(1, int(usable_h / line_h))

        idx = 0
        while idx < len(lines):
            y = ensure_space(y, per_page_box_h)
            block_h = per_page_box_h

            pdf.setStrokeColor(border)
            pdf.setFillColor(colors.white)
            pdf.rect(page_margin_x, y - block_h, content_w, block_h, fill=1, stroke=1)

            # left accent
            pdf.setFillColor(primary)
            pdf.rect(page_margin_x, y - block_h, 0.10 * inch, block_h, fill=1, stroke=0)

            pdf.setFillColor(colors.HexColor("#f0fdfa"))
            pdf.rect(page_margin_x + 0.10 * inch, y - label_h, content_w - 0.10 * inch, label_h, fill=1, stroke=0)

            pdf.setFillColor(dark_accent)
            pdf.setFont("Helvetica-Bold", 10)
            title = "Patient-Friendly Medication Explanation" + (" (contd.)" if idx > 0 else "")
            pdf.drawString(page_margin_x + 0.12 * inch, y - 0.20 * inch, title)

            pdf.setFont(body_font, 9)
            pdf.setFillColor(header_text)
            text_x = page_margin_x + 0.18 * inch
            y_cursor = y - 0.45 * inch

            take = lines[idx : idx + max_lines]
            for ln in take:
                pdf.drawString(text_x, y_cursor, ln[:180])
                y_cursor -= line_h

            idx += len(take)
            y = y - block_h - 0.35 * inch

        return y

    def draw_validation_summary(y: float) -> float:
        meds = prescription.medicines or []
        missing_fields = 0
        low_conf = 0
        names = []
        for m in meds:
            nm = (m.normalized_name or m.original_name or "").strip().lower()
            if nm:
                names.append(nm)
            if not (m.dose and str(m.dose).strip()) or not (m.frequency and str(m.frequency).strip()) or not (m.duration_days and m.duration_days > 0):
                missing_fields += 1
            conf_val = m.confidence if m.confidence is not None else 0.0
            conf_pct = conf_val * 100.0 if conf_val <= 1.0 else conf_val
            if conf_pct < 60:
                low_conf += 1

        dup_count = len(names) - len(set(names))
        allergies = str(patient_details.get("allergies") or "").strip().lower()
        allergy_hits = 0
        if allergies:
            for nm in set(names):
                if nm and any(a.strip() and a.strip() in nm for a in allergies.replace(",", " ").split()):
                    allergy_hits += 1

        status = "✓ No critical issues"
        if allergy_hits > 0 or low_conf > 0:
            status = "⚠ Minor review recommended"
        if allergy_hits > 0 and low_conf > 0:
            status = "❗ Requires doctor verification"

        lines = [
            f"Dose range validation: Not available",
            f"Duplicate drug detection: {'Detected' if dup_count > 0 else 'None'}",
            f"Interaction check: Not available",
            f"Allergy check: {'Possible conflicts' if allergy_hits > 0 else 'No conflicts detected'}",
            f"Missing field warnings: {missing_fields} medicine(s) missing dose/frequency/duration" if meds else "Missing field warnings: No medicines extracted",
            f"Overall status: {status}",
        ]

        wrapped = []
        for ln in lines:
            wrapped.extend(wrap_lines(ln, body_font, 9, content_w - 0.30 * inch)[:2])
        label_h = 0.30 * inch
        line_h = 0.22 * inch
        block_h = label_h + 0.22 * inch + (len(wrapped) * line_h) + 0.12 * inch
        y = ensure_space(y, block_h + 0.30 * inch)

        pdf.setStrokeColor(border)
        pdf.setFillColor(colors.white)
        pdf.rect(page_margin_x, y - block_h, content_w, block_h, fill=1, stroke=1)

        pdf.setFillColor(colors.HexColor("#f0fdfa"))
        pdf.rect(page_margin_x, y - 0.30 * inch, content_w, 0.30 * inch, fill=1, stroke=0)
        pdf.setFillColor(dark_accent)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(page_margin_x + 0.12 * inch, y - 0.22 * inch, "Clinical Validation Summary")

        pdf.setFont(body_font, 9)
        pdf.setFillColor(header_text)
        y_cur = y - 0.52 * inch
        for wline in wrapped:
            pdf.drawString(page_margin_x + 0.12 * inch, y_cur, wline)
            y_cur -= 0.22 * inch

        return y - block_h - 0.30 * inch

    def draw_confidence_table(y: float) -> float:
        y = ensure_space(y, 1.6 * inch)
        block_h = 1.35 * inch
        x = page_margin_x
        w = content_w
        pdf.setFillColor(colors.white)
        pdf.rect(page_margin_x, y - block_h, content_w, block_h, fill=1, stroke=1)

        label_h = 0.28 * inch
        pdf.setFillColor(colors.HexColor("#f3f4f6"))
        pdf.rect(page_margin_x, y - label_h, content_w * 0.55, label_h, fill=1, stroke=0)
        pdf.setFillColor(dark_accent)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(page_margin_x + 0.12 * inch, y - 0.20 * inch, "Confidence Interpretation")

        rows = [
            ("95–100%", "No verification required"),
            ("80–95%", "Optional verification"),
            ("60–80%", "Recommended verification"),
            ("Below 60%", "Mandatory verification"),
        ]

        pdf.setFont(body_font, 9)
        pdf.setFillColor(header_text)
        y_cursor = y - 0.55 * inch
        for rng, meaning in rows:
            pdf.setFillColor(muted)
            pdf.drawString(page_margin_x + 0.12 * inch, y_cursor, rng)
            pdf.setFillColor(header_text)
            pdf.drawString(page_margin_x + 1.20 * inch, y_cursor, meaning)
            y_cursor -= 0.24 * inch

        return y - block_h - 0.30 * inch

    draw_page_bg()
    draw_header()

    y = content_top_y
    y = draw_patient_doctor_cards(y)
    y = draw_medicines_table(y)
    y = draw_patient_friendly_explanation(y)
    y = draw_validation_summary(y)
    y = draw_adherence_summary(y)
    y = draw_confidence_table(y)

    draw_footer()

    pdf.save()
    buffer.seek(0)
    return buffer.read()
