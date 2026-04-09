from __future__ import annotations

from html import escape
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent
FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_NAME = "DejaVuSans"


def shape_ar(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def p(text: str, style: ParagraphStyle, arabic: bool = False) -> Paragraph:
    value = shape_ar(text) if arabic else text
    value = escape(value).replace("\n", "<br/>")
    return Paragraph(value, style)


def bullet_table(items: list[tuple[str, bool]], style: ParagraphStyle) -> Table:
    rows = []
    for item, is_arabic in items:
        rows.append(
            [
                Paragraph("•", style),
                p(item, style, arabic=is_arabic),
            ]
        )
    table = Table(rows, colWidths=[10 * mm, 160 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_doc(data: dict, output_path: Path) -> None:
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "Base",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#1b1b1f"),
        alignment=TA_LEFT,
    )
    small = ParagraphStyle("Small", parent=base, fontSize=9.2, leading=13)
    title = ParagraphStyle(
        "Title",
        parent=base,
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#101826"),
        spaceAfter=6,
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=base,
        fontSize=11.5,
        leading=16,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=12,
    )
    section = ParagraphStyle(
        "Section",
        parent=base,
        fontSize=12.5,
        leading=18,
        textColor=colors.HexColor("#0f4c81"),
        spaceBefore=8,
        spaceAfter=5,
    )
    chip = ParagraphStyle(
        "Chip",
        parent=small,
        textColor=colors.HexColor("#0f4c81"),
    )

    story = [
        p(data["brand_name"], title),
        p(data["tagline"], subtitle),
    ]

    summary_table = Table(
        [
            [
                p("<b>Category</b>", chip),
                p(data["category"], base),
                p("<b>Primary Market</b>", chip),
                p(data["market"], base),
            ],
            [
                p("<b>Primary Goal</b>", chip),
                p(data["goal"], base),
                p("<b>Language Profile</b>", chip),
                p(data["language_profile_line"], base),
            ],
        ],
        colWidths=[28 * mm, 62 * mm, 34 * mm, 48 * mm],
        hAlign="LEFT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f8fb")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d6dbe3")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story += [summary_table, Spacer(1, 7 * mm)]

    sections = [
        ("Audience", data["audience"]),
        ("Positioning", data["positioning"]),
        ("Core Offer", data["offer"]),
        ("SEO Keywords", data["seo_keywords"]),
        ("Voice Rules", data["voice_rules"]),
        ("Do / Avoid", data["do_avoid"]),
        ("Caption Examples", data["caption_examples"]),
        ("Visual Direction", data["visual_direction"]),
        ("CTA Rules", data["cta_rules"]),
    ]

    for heading, items in sections:
        story.append(p(heading, section))
        story.append(bullet_table(items, base))

    story.append(Spacer(1, 4 * mm))
    story.append(p("Language Profile JSON", section))
    story.append(
        Table(
            [[p(data["language_json"], small)]],
            colWidths=[182 * mm],
            hAlign="LEFT",
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0b1220")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#e5eefb")),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#20324d")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        )
    )

    doc.build(story)


def main() -> None:
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))

    briefs = [
        {
            "filename": "01_Burger_Chain_Client_Brief.pdf",
            "brand_name": "Stack District",
            "tagline": "Premium smash-burger chain brief for a Kuwait delivery-first concept.",
            "category": "Burger Chain / Fast Casual",
            "market": "Kuwait",
            "goal": "Drive delivery orders, combo upsells, and repeat late-night demand.",
            "language_profile_line": "Brief in English, captions generated in Arabic (Gulf).",
            "audience": [
                ("Men and women ages 18-34 in Kuwait who want indulgent comfort food that still feels premium, urban, and social-media worthy.", False),
                ("Office workers ordering lunch, friend groups ordering late at night, and students who respond to craveable visuals and direct offers.", False),
            ],
            "positioning": [
                ("Stack District is not cheap fast food. It is a high-crave, premium-feeling burger lane built around heat, texture, and visual appetite.", False),
                ("The brand should feel bold, playful, fast-moving, and confidently modern.", False),
            ],
            "offer": [
                ("Double smash burgers, loaded fries, signature sauces, limited-time combos, and fast delivery bundles.", False),
                ("Push high-margin add-ons: fries upgrade, drink pairing, extra sauce, dessert attachment.", False),
            ],
            "seo_keywords": [
                ("best burger kuwait", False),
                ("smash burger kuwait", False),
                ("late night burger delivery kuwait", False),
                ("loaded fries kuwait", False),
                ("مطعم برجر الكويت", True),
                ("برجر دليفري الكويت", True),
            ],
            "voice_rules": [
                ("Energetic, crave-led, visual, and fast. Short sentences beat long explanations.", False),
                ("Emoji-friendly when posting offers or indulgent launches. Use them lightly, not like spam.", False),
                ("Never sound childish or discount-bin. Premium fun, not cheap noise.", False),
            ],
            "do_avoid": [
                ("Do use appetite words: melt, crisp, loaded, stacked, seared, late-night, bold.", False),
                ("Do use direct action CTAs for ordering now.", False),
                ("Avoid corporate food language, dry ingredient listing, or fake gourmet clichés.", False),
            ],
            "caption_examples": [
                ("جاهز لبرجر يضرب من أول لقمة؟ ستاك ديستركت يجمع بين اللحم السماش، الجبن السايح، والخبز المحمّص بطريقة تخليك تعيد الطلب مرة ثانية. اطلب الآن وخلك في مزاج البرجر الصح. 🍔🔥", True),
                ("ليلة طويلة؟ خل الطلب يستاهلها. كومبو ستاك ديستركت يعطيك البرجر + البطاط + المشروب في وجبة وحدة تشبعك وتبان فخمة بنفس الوقت. اطلبها الآن.", True),
                ("مو كل برجر ينذكر. في برجر يترك أثر. ستاك ديستركت للناس اللي تبغى طعم واضح وصورة تشهي من أول ثانية.", True),
            ],
            "visual_direction": [
                ("Tight burger close-ups, sauce pull, cheese melt, crispy fry texture, dark premium backgrounds, fast delivery lifestyle shots.", False),
                ("Avoid sterile white food photography unless it is for a menu explainer post.", False),
            ],
            "cta_rules": [
                ("Primary CTA: Order now.", False),
                ("Secondary CTA: Try the combo / add fries / save this for tonight.", False),
            ],
            "language_json": '{<br/>  "brief_language": "english",<br/>  "primary_language": "arabic",<br/>  "caption_output_language": "arabic",<br/>  "arabic_mode": "gulf"<br/>}',
        },
        {
            "filename": "02_Vehicles_Client_Brief.pdf",
            "brand_name": "Vantage Auto",
            "tagline": "Premium vehicle reseller brief focused on credibility, inventory quality, and clean English conversion copy.",
            "category": "Vehicles / Premium Resale",
            "market": "Kuwait",
            "goal": "Generate serious buyer inquiries for inspected SUVs and executive sedans.",
            "language_profile_line": "Brief in English, captions generated in English.",
            "audience": [
                ("Professionals, family buyers, and status-conscious drivers ages 27-48 looking for clean, trusted, premium used vehicles.", False),
                ("The buyer wants certainty, service history, clean condition, and a dealership that feels transparent and sharp.", False),
            ],
            "positioning": [
                ("Vantage Auto sells confidence, not just cars. Every listing should feel verified, premium, and ready to own.", False),
                ("The tone should feel composed, masculine or executive-leaning depending on the vehicle, and always credible.", False),
            ],
            "offer": [
                ("Inspected inventory, clean-condition SUVs, executive sedans, finance guidance, and trade-in conversations.", False),
                ("Highlight mileage, condition, service history, trim level, and why the car fits a specific buyer profile.", False),
            ],
            "seo_keywords": [
                ("used suv kuwait", False),
                ("luxury cars kuwait", False),
                ("lexus kuwait used", False),
                ("family suv kuwait", False),
                ("cars for sale kuwait", False),
            ],
            "voice_rules": [
                ("Direct, premium, factual. No exaggerated hype.", False),
                ("No emoji in standard inventory posts. Clean English only.", False),
                ("If urgency is used, it should feel real: limited unit, fast-moving listing, clean example.", False),
            ],
            "do_avoid": [
                ("Do mention condition, trim, inspection, ownership fit, and premium details.", False),
                ("Do make the caption feel like a serious buying opportunity.", False),
                ("Avoid slang, teenage energy, and vague claims like best ever or crazy deal.", False),
            ],
            "caption_examples": [
                ("A clean SUV should feel decisive before the test drive even starts. This unit combines road presence, interior comfort, and the kind of condition serious buyers notice immediately. Message now to book a viewing.", False),
                ("For buyers who want executive presence without unnecessary noise: sharp exterior, disciplined condition, and a cabin that still feels premium. Enquire now for full details and inspection notes.", False),
                ("Not every listed vehicle is worth your time. This one is. Clean condition, strong stance, and a spec that fits daily use without losing prestige.", False),
            ],
            "visual_direction": [
                ("Three-quarter hero shots, front grille detail, interior steering/cabin shots, wheel close-ups, and polished outdoor dealership light.", False),
                ("Avoid over-editing, fake luxury overlays, or childish automotive memes.", False),
            ],
            "cta_rules": [
                ("Primary CTA: Message for viewing / enquire now.", False),
                ("Secondary CTA: Ask for inspection details / reserve this unit.", False),
            ],
            "language_json": '{<br/>  "brief_language": "english",<br/>  "primary_language": "english",<br/>  "caption_output_language": "english",<br/>  "arabic_mode": ""<br/>}',
        },
        {
            "filename": "03_Fashion_Client_Brief.pdf",
            "brand_name": "Liné Atelier",
            "tagline": "Refined fashion brief built for a bilingual luxury-ready social presence.",
            "category": "Fashion / Contemporary Womenswear",
            "market": "Kuwait + GCC",
            "goal": "Build desire, save-worthy content, and high-intent DM inquiries for new drops and edited looks.",
            "language_profile_line": "Brief in English, captions generated in bilingual mode.",
            "audience": [
                ("Women ages 22-39 who buy fashion as a statement of taste, restraint, and identity rather than loud trend-chasing.", False),
                ("They respond to elegance, styling clarity, premium visuals, and a label that feels editorial rather than mass-market.", False),
            ],
            "positioning": [
                ("Liné Atelier stands for quiet confidence, tailored femininity, and modern pieces that look expensive without trying too hard.", False),
                ("The brand should feel editorial, sophisticated, feminine, and controlled.", False),
            ],
            "offer": [
                ("Seasonal drops, occasionwear, elevated day sets, structured silhouettes, and limited-run capsule edits.", False),
                ("Push craftsmanship, silhouette, texture, styling ease, and the feeling of entering the room already composed.", False),
            ],
            "seo_keywords": [
                ("fashion boutique kuwait", False),
                ("luxury dresses kuwait", False),
                ("women clothing kuwait", False),
                ("contemporary abaya kuwait", False),
                ("بوتيك أزياء الكويت", True),
                ("فساتين فاخرة الكويت", True),
            ],
            "voice_rules": [
                ("Refined, understated, image-led. Elegant language over loud selling.", False),
                ("Emoji may appear in launch or styling posts, but keep it minimal and tasteful: ✨ is acceptable, clutter is not.", False),
                ("Bilingual captions should feel intentionally written, not machine-translated line by line.", False),
            ],
            "do_avoid": [
                ("Do use words like tailored, refined, sculpted, fluid, quiet confidence, editorial, elevated.", False),
                ("Do make the reader imagine how she will feel wearing the piece.", False),
                ("Avoid bargain language, cheap urgency, or trend-chasing slang.", False),
            ],
            "caption_examples": [
                ("Tailored lines. Quiet confidence. A piece designed to enter the room before you speak. ✨\nتصميم يمنحك حضورًا هادئًا وواضحًا من أول نظرة.", False),
                ("Some looks do not need noise to be remembered.\nبعض الإطلالات لا تحتاج ضجيجًا حتى تبقى في الذاكرة.", False),
                ("An elevated silhouette for women who prefer precision over excess.\nقصة أنيقة للمرأة التي تختار الدقة بدل المبالغة.", False),
            ],
            "visual_direction": [
                ("Editorial lighting, movement in fabric, detail crops on seams and texture, neutral luxury sets, and poised model posture.", False),
                ("Avoid busy sale graphics, loud stickers, or collage-heavy retail visuals.", False),
            ],
            "cta_rules": [
                ("Primary CTA: Discover the drop / DM to reserve / shop the edit.", False),
                ("Secondary CTA: Save this look / share with someone styling Ramadan, Eid, events, or evening occasions.", False),
            ],
            "language_json": '{<br/>  "brief_language": "english",<br/>  "primary_language": "bilingual",<br/>  "caption_output_language": "bilingual",<br/>  "arabic_mode": "gulf"<br/>}',
        },
    ]

    for brief in briefs:
        build_doc(brief, ROOT / brief["filename"])


if __name__ == "__main__":
    main()
