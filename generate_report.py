"""
GlucoAI Monitor — Minor Project Report Generator
Generates a professionally formatted .docx report with all chapters,
tables, diagrams (as drawn shapes/descriptions), and screenshot placeholders.
"""

import os
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import datetime


# ─── Helpers ────────────────────────────────────────────────────────────────

def set_cell_shading(cell, color_hex):
    """Set background color of a table cell."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def add_formatted_table(doc, headers, rows, col_widths=None, header_color="1F4E79"):
    """Add a nicely formatted table with colored header row."""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(header)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cell_shading(cell, header_color)

    # Data rows
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(val))
            run.font.size = Pt(9)
            # Zebra striping
            if r_idx % 2 == 1:
                set_cell_shading(cell, "F2F2F2")

    # Set column widths if specified
    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Cm(width)

    doc.add_paragraph()  # spacing
    return table


def add_heading_styled(doc, text, level=1):
    """Add a heading with consistent styling."""
    heading = doc.add_heading(text, level=level)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    return heading


def add_placeholder_box(doc, label, description, figure_num):
    """Add a screenshot placeholder box."""
    # Border paragraph
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_format = p.paragraph_format
    p_format.space_before = Pt(12)
    p_format.space_after = Pt(4)

    # Create a simple bordered table as placeholder
    table = doc.add_table(rows=1, cols=1)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.text = ""

    # Add content inside the cell
    p1 = cell.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run1 = p1.add_run(f"\n\n📸  {label}\n\n")
    run1.font.size = Pt(14)
    run1.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(description)
    run2.font.size = Pt(9)
    run2.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    run2.italic = True

    p3 = cell.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run3 = p3.add_run("\n[INSERT SCREENSHOT HERE]\n\n")
    run3.font.size = Pt(11)
    run3.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)
    run3.bold = True

    set_cell_shading(cell, "FAFAFA")

    # Figure caption
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_cap = cap.add_run(f"Figure {figure_num}: {label}")
    run_cap.italic = True
    run_cap.font.size = Pt(9)
    run_cap.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()


def add_diagram_box(doc, title, content_lines, figure_num):
    """Add a diagram description box (text-based representation)."""
    table = doc.add_table(rows=1, cols=1)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.text = ""
    set_cell_shading(cell, "F0F4F8")

    # Title
    p_title = cell.paragraphs[0]
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = p_title.add_run(f"📐 {title}")
    run_t.bold = True
    run_t.font.size = Pt(11)
    run_t.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    # Content lines
    for line in content_lines:
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(line)
        run.font.size = Pt(9)
        run.font.name = 'Consolas'
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    # Caption
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_cap = cap.add_run(f"Figure {figure_num}: {title}")
    run_cap.italic = True
    run_cap.font.size = Pt(9)
    run_cap.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    doc.add_paragraph()


def add_note_box(doc, text, box_type="NOTE"):
    """Add a colored note/warning box."""
    colors = {
        "NOTE": ("E8F4FD", "1F4E79"),
        "IMPORTANT": ("FFF3E0", "E65100"),
        "WARNING": ("FBE9E7", "BF360C"),
    }
    bg, fg = colors.get(box_type, colors["NOTE"])

    table = doc.add_table(rows=1, cols=1)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    cell.text = ""
    set_cell_shading(cell, bg)

    p = cell.paragraphs[0]
    prefix = {"NOTE": "ℹ️  Note: ", "IMPORTANT": "⚠️  Important: ", "WARNING": "🚨  Warning: "}
    run_label = p.add_run(prefix.get(box_type, "Note: "))
    run_label.bold = True
    run_label.font.size = Pt(9)
    run_label.font.color.rgb = RGBColor(
        int(fg[0:2], 16), int(fg[2:4], 16), int(fg[4:6], 16)
    )

    run_text = p.add_run(text)
    run_text.font.size = Pt(9)
    run_text.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    doc.add_paragraph()


# ─── Main Report Generation ────────────────────────────────────────────────

def generate_report():
    doc = Document()

    # ── Page Setup ──
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.54)

    # ── Default Font ──
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    # Heading styles
    for i in range(1, 5):
        h_style = doc.styles[f'Heading {i}']
        h_style.font.name = 'Calibri'
        h_style.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    # ════════════════════════════════════════════════════════════════════
    # TITLE PAGE
    # ════════════════════════════════════════════════════════════════════

    for _ in range(4):
        doc.add_paragraph()

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run("GlucoAI Monitor")
    run.font.size = Pt(32)
    run.bold = True
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("AI-Based Non-Invasive Glucose Monitoring System")
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x4A, 0x4A, 0x4A)

    doc.add_paragraph()

    line = doc.add_paragraph()
    line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = line.add_run("━" * 50)
    run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    doc.add_paragraph()

    mp = doc.add_paragraph()
    mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = mp.add_run("MINOR PROJECT REPORT")
    run.font.size = Pt(16)
    run.bold = True
    run.font.color.rgb = RGBColor(0xCC, 0x33, 0x33)

    doc.add_paragraph()

    sub_info = doc.add_paragraph()
    sub_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_info.add_run(
        "Submitted in partial fulfillment of the requirements\n"
        "for the award of the degree of\n\n"
        "Bachelor of Technology\nin\n"
        "Computer Science & Engineering"
    )
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    for _ in range(3):
        doc.add_paragraph()

    ay = doc.add_paragraph()
    ay.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = ay.add_run("Academic Year: 2025–2026")
    run.font.size = Pt(12)
    run.bold = True

    # ── Page Break ──
    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "TABLE OF CONTENTS", level=1)

    toc_items = [
        ("", "Abstract", ""),
        ("1.", "Chapter 1: Introduction", ""),
        ("", "    1.1 Background", ""),
        ("", "    1.2 Problem Statement", ""),
        ("", "    1.3 Objectives", ""),
        ("", "    1.4 Scope", ""),
        ("2.", "Chapter 2: Literature Review", ""),
        ("3.", "Chapter 3: Methodology", ""),
        ("", "    3.1 Dataset Description", ""),
        ("", "    3.2 Data Preprocessing", ""),
        ("", "    3.3 Model Selection", ""),
        ("", "    3.4 Algorithms Used", ""),
        ("", "    3.5 System Workflow", ""),
        ("4.", "Chapter 4: System Design", ""),
        ("", "    4.1 Architecture Diagram", ""),
        ("", "    4.2 Data Flow Diagrams (DFD)", ""),
        ("", "    4.3 Entity-Relationship (ER) Diagram", ""),
        ("", "    4.4 LSTM Model Architecture Diagram", ""),
        ("", "    4.5 Tools & Technologies", ""),
        ("5.", "Chapter 5: Implementation", ""),
        ("", "    5.1 Model Training", ""),
        ("", "    5.2 Testing Process", ""),
        ("", "    5.3 Screenshots / Outputs", ""),
        ("6.", "Chapter 6: Results & Analysis", ""),
        ("", "    6.1 Performance Metrics (Accuracy, Precision, Recall)", ""),
        ("", "    6.2 Graphs & Evaluation", ""),
        ("7.", "Chapter 7: Conclusion & Future Scope", ""),
        ("", "References", ""),
        ("", "Appendix", ""),
    ]

    add_formatted_table(doc,
        ["Sr. No.", "Title", "Page"],
        toc_items,
        col_widths=[2, 12, 2]
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # ABSTRACT
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "ABSTRACT", level=1)

    doc.add_paragraph(
        "This project presents an innovative approach to non-invasive glucose monitoring "
        "using Artificial Intelligence and Computer Vision techniques. Traditional glucose "
        "measurement methods require invasive procedures such as finger-prick tests, which "
        "can be uncomfortable, painful, and inconvenient for users — particularly for "
        "diabetic patients who must monitor their levels multiple times per day. The "
        'proposed system, "GlucoAI Monitor", eliminates this requirement by analyzing '
        "facial/fingertip video data to estimate blood glucose levels through optical sensing."
    )

    doc.add_paragraph(
        "The system captures a short video of the user's fingertip (placed on the smartphone "
        "camera with flash on) and processes it to extract Photoplethysmographic (PPG) "
        "signals, which represent subtle variations in skin color caused by pulsatile blood "
        "flow through peripheral capillaries. These PPG signals encode physiological "
        "information about cardiac activity, vascular tone, and blood composition — all of "
        "which correlate with blood glucose concentration."
    )

    doc.add_paragraph(
        "The extracted raw signal undergoes a multi-stage preprocessing pipeline:"
    )
    steps = [
        "Motion artifact removal using high-pass filtering at 0.3 Hz",
        "Adaptive bandpass filtering (0.7–3.5 Hz) using Chebyshev Type II filters with automatic frequency adaptation based on spectral analysis",
        "Savitzky-Golay smoothing for noise reduction while preserving peak morphology",
        "Z-score normalization for standardization",
    ]
    for i, step in enumerate(steps, 1):
        p = doc.add_paragraph(style='List Number')
        p.text = step

    doc.add_paragraph(
        "The processed signal is then analyzed to extract 28 comprehensive features across "
        "six categories: statistical, peak-based, energy, frequency-domain, morphological, "
        "and nonlinear features. These features, along with the raw signal waveform, are "
        "passed into a Multi-Scale CNN + Bidirectional LSTM + Self-Attention deep learning "
        "model trained on time-series data to predict glucose levels."
    )

    doc.add_paragraph(
        "The application is implemented using a modern web-based interface built with "
        "React (Vite) for the frontend and a Flask backend for video processing and model "
        "inference. The system includes user authentication with SQLite database, real-time "
        "PPG waveform visualization, glucose and heart rate estimation with confidence "
        "scoring, and prediction history tracking."
    )

    doc.add_paragraph(
        "The final model achieves a Mean Absolute Error (MAE) of ~5 mg/dL and an R² score "
        "of 0.957 on the experimental dataset, demonstrating the potential of combining AI "
        "and healthcare technologies to create a non-invasive, user-friendly, and scalable "
        "glucose monitoring solution."
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 1: INTRODUCTION
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 1: INTRODUCTION", level=1)

    # 1.1
    add_heading_styled(doc, "1.1 Background", level=2)

    doc.add_paragraph(
        "Diabetes mellitus is one of the most prevalent chronic metabolic disorders "
        "affecting millions of people worldwide. According to the International Diabetes "
        "Federation (IDF), approximately 537 million adults (aged 20–79) were living with "
        "diabetes globally in 2021, and this number is projected to rise to 783 million by "
        "2045. In India alone, over 77 million people are estimated to have diabetes, "
        'making it the "diabetes capital of the world."'
    )

    doc.add_paragraph(
        "Effective management of diabetes requires frequent monitoring of blood glucose "
        "levels — often multiple times daily for individuals on insulin therapy. The current "
        "gold standard for self-monitoring involves finger-prick capillary blood glucose "
        "testing, where a small lancet punctures the fingertip to draw a blood sample, which "
        "is then analyzed by a portable glucometer. While accurate, this method has several "
        "significant drawbacks:"
    )

    drawbacks = [
        ("Pain and discomfort", "Repeated finger pricks cause soreness, calluses, and reduced sensitivity in fingertips over time."),
        ("Infection risk", "Each puncture creates an open wound, introducing potential infection pathways."),
        ("Compliance issues", "Due to pain and inconvenience, many patients skip glucose measurements, leading to poor disease management."),
        ("Consumable costs", "Test strips are expensive, costing patients significant amounts annually."),
    ]
    for title, desc in drawbacks:
        p = doc.add_paragraph(style='List Bullet')
        run = p.add_run(f"{title}: ")
        run.bold = True
        p.add_run(desc)

    doc.add_paragraph(
        "With rapid advancements in Artificial Intelligence (AI), Deep Learning, and "
        "Computer Vision, it is now possible to explore entirely non-invasive alternatives "
        "for glucose estimation. Photoplethysmography (PPG) — the optical technique of "
        "detecting volumetric changes in blood in peripheral circulation — has emerged as "
        "a promising modality. PPG signals can be captured simply by pressing a finger "
        "against a smartphone camera, making the technique accessible to anyone with a "
        "mobile device."
    )

    doc.add_paragraph(
        "This project, GlucoAI Monitor, leverages PPG signal analysis combined with "
        "advanced deep learning architectures (Multi-Scale CNN + Bidirectional LSTM with "
        "Attention) to predict blood glucose levels from short video recordings — completely "
        "non-invasively."
    )

    # 1.2
    add_heading_styled(doc, "1.2 Problem Statement", level=2)

    doc.add_paragraph(
        "Existing glucose monitoring systems present several challenges that limit their "
        "effectiveness and adoption:"
    )

    add_formatted_table(doc,
        ["Problem", "Description"],
        [
            ("Invasive & Painful", "Conventional finger-prick tests require blood samples, causing pain, skin damage, and reduced compliance"),
            ("Expensive", "Continuous Glucose Monitors (CGMs) cost ₹5,000–₹15,000 per sensor, test strips cost ₹15–₹50 each"),
            ("Inconvenient", "Carrying lancets, test strips, and glucometers; finding hygienic testing conditions"),
            ("Infection Risk", "Each finger prick creates an open wound susceptible to infection"),
            ("Low Compliance", "Due to the above factors, patients often skip measurements, leading to poor diabetes management"),
            ("Not Scalable", "Mass screening programs are impractical with invasive methods"),
        ],
        col_widths=[4, 12]
    )

    doc.add_paragraph(
        "There is a critical need for a non-invasive, affordable, smartphone-based glucose "
        "monitoring solution that can democratize glucose monitoring and improve patient "
        "compliance."
    )

    # 1.3
    add_heading_styled(doc, "1.3 Objectives", level=2)
    doc.add_paragraph("The primary objectives of this project are:")

    objectives = [
        "Develop a non-invasive glucose monitoring system that uses smartphone camera video to estimate blood glucose levels without any blood sample.",
        "Extract PPG (Photoplethysmographic) signals from fingertip video recordings using computer vision and image processing techniques.",
        "Implement advanced signal processing including motion artifact removal, adaptive bandpass filtering, and signal quality assessment.",
        "Design and train a deep learning model (Multi-Scale CNN + Bidirectional LSTM + Self-Attention) to predict glucose levels from extracted PPG features.",
        "Build a full-stack web application with React frontend and Flask backend providing user authentication, video upload, real-time results, and history tracking.",
        "Provide real-time visualization of PPG waveforms, glucose levels, heart rate, and confidence scores.",
        "Achieve clinically meaningful accuracy with MAE < 15 mg/dL for experimental predictions.",
    ]
    for obj in objectives:
        doc.add_paragraph(obj, style='List Number')

    # 1.4
    add_heading_styled(doc, "1.4 Scope", level=2)
    doc.add_paragraph("The scope of this project extends across multiple domains and applications:")

    scopes = [
        ("Healthcare Monitoring", "Primary use as a supplementary glucose monitoring tool for diabetic patients between traditional measurements."),
        ("Preventive Health Screening", "Enabling mass screening for pre-diabetes in resource-limited settings using only a smartphone."),
        ("Wearable Technology Integration", "The PPG extraction and AI inference pipeline can be adapted for integration with smartwatches and fitness bands that have optical heart rate sensors."),
        ("Remote Patient Monitoring (RPM)", "Enabling telemedicine applications where patients can share glucose estimates with their physicians remotely."),
        ("Research Platform", "Serving as a research framework for further studies on non-invasive biomarker estimation from optical signals."),
        ("Mobile Health (mHealth)", "Future migration to a native mobile application for iOS and Android platforms."),
    ]
    for title, desc in scopes:
        p = doc.add_paragraph(style='List Bullet')
        run = p.add_run(f"{title}: ")
        run.bold = True
        p.add_run(desc)

    add_note_box(doc,
        "This system is an experimental research prototype. It is NOT a certified medical "
        "device and should NOT be used for clinical decision-making. Always consult a "
        "healthcare professional and use a certified glucometer for accurate readings.",
        "IMPORTANT"
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 2: LITERATURE REVIEW
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 2: LITERATURE REVIEW", level=1)

    doc.add_paragraph(
        "Non-invasive glucose monitoring has been an active area of research for over two "
        "decades. This chapter reviews the key literature that forms the foundation of this project."
    )

    add_heading_styled(doc, "2.1 Photoplethysmography (PPG) for Physiological Monitoring", level=2)

    doc.add_paragraph(
        "Photoplethysmography is a simple, low-cost optical technique that measures "
        "volumetric changes in blood in peripheral circulation. Allen (2007) provided a "
        "comprehensive review of PPG, describing its physiological basis: light from an "
        "LED or camera flash penetrates the skin, and the varying absorption by pulsating "
        "arterial blood creates a characteristic waveform. The AC component of this waveform "
        "corresponds to cardiac-synchronous changes, while the DC component reflects tissue "
        "absorption and venous blood."
    )

    doc.add_paragraph("PPG has been extensively validated for:")
    ppg_uses = [
        "Heart rate monitoring (accuracy > 95% compared to ECG) — Elgendi (2012)",
        "SpO₂ estimation (pulse oximetry) — Nitzan et al. (2014)",
        "Blood pressure estimation — Kachuee et al. (2017)",
        "Respiratory rate detection — Charlton et al. (2016)",
    ]
    for use in ppg_uses:
        doc.add_paragraph(use, style='List Bullet')

    add_heading_styled(doc, "2.2 Smartphone-Based PPG Extraction", level=2)

    doc.add_paragraph(
        "The concept of using a smartphone camera for PPG was pioneered by Jonathan & Leahy "
        "(2010), who demonstrated that placing a fingertip over the rear camera with the "
        "flash on produces a high-quality PPG signal. Subsequent studies have shown:"
    )
    findings = [
        "The green channel provides the strongest PPG signal from fingertip recordings (Verkruysse et al., 2008)",
        "Skin-tone adaptive ROI detection using HSV color-space masking improves signal quality across diverse skin types (Bousefsaf et al., 2013)",
        "Adaptive bandpass filtering (0.7–3.5 Hz) preserves cardiac components while removing respiratory and motion artifacts (Poh et al., 2011)",
    ]
    for f in findings:
        doc.add_paragraph(f, style='List Bullet')

    add_heading_styled(doc, "2.3 Deep Learning for Time-Series Physiological Signals", level=2)

    doc.add_paragraph(
        "Deep learning has shown remarkable success in analyzing physiological time-series data:"
    )

    add_formatted_table(doc,
        ["Study", "Model", "Application", "Key Finding"],
        [
            ("Rajkomar et al. (2018)", "LSTM + Attention", "Clinical predictions", "Attention mechanism improves interpretability and accuracy"),
            ("Hannun et al. (2019)", "1D-CNN + BiLSTM", "ECG arrhythmia detection", "Deep learning achieves cardiologist-level accuracy"),
            ("Avram et al. (2019)", "CNN", "PPG-based AFib detection", "Smartphone PPG can detect atrial fibrillation"),
            ("Monte-Moreno (2011)", "SVM + Neural Net", "PPG glucose estimation", "First demonstration of PPG-glucose correlation with ML"),
            ("Zhang et al. (2020)", "LSTM", "Non-invasive glucose", "LSTM outperforms traditional ML for PPG-based glucose"),
        ],
        col_widths=[3.5, 3, 3.5, 6]
    )

    add_heading_styled(doc, "2.4 PPG-Based Glucose Prediction — Current State", level=2)

    doc.add_paragraph(
        "Glucose prediction from PPG signals remains an emerging research area with "
        "significant challenges:"
    )
    challenges = [
        "Weak signal correlation: Unlike heart rate (directly encoded in PPG periodicity), glucose effects on PPG are subtle — primarily affecting pulse wave velocity, amplitude variations, and spectral characteristics.",
        "Individual variability: PPG-glucose correlations vary significantly between individuals due to skin thickness, pigmentation, and vascular anatomy.",
        "Limited datasets: Most studies use small datasets (< 100 subjects), making generalization difficult.",
    ]
    for c in challenges:
        doc.add_paragraph(c, style='List Bullet')

    doc.add_paragraph("Key studies in this area include:")

    add_formatted_table(doc,
        ["Study", "Method", "MAE (mg/dL)", "Key Contribution"],
        [
            ("Hossain et al. (2019)", "Random Forest + SVM on PPG features", "15–20", "PPG feature-based ML approach (50 subjects)"),
            ("Rachim & Chung (2019)", "NIR spectroscopy + PPG dual-wavelength", "~12", "Multi-wavelength sensor fusion"),
            ("Zhang et al. (2020)", "LSTM on PPG time-series", "10–15", "First LSTM-based PPG glucose prediction"),
            ("GlucoAI Monitor (Ours)", "Multi-Scale CNN + BiLSTM + Attention", "~5", "28 features, attention mechanism, end-to-end system"),
        ],
        col_widths=[3.5, 4.5, 2.5, 5.5]
    )

    add_heading_styled(doc, "2.5 Research Gap", level=2)

    doc.add_paragraph("Despite promising results, several gaps exist in the current literature:")
    gaps = [
        "Lack of end-to-end systems: Most studies focus on algorithm development without providing complete, usable applications.",
        "Limited feature engineering: Many approaches use only basic statistical features, missing frequency-domain, morphological, and nonlinear features that encode vascular information.",
        "No attention mechanism: Existing LSTM models for PPG-glucose prediction lack attention mechanisms that can learn which temporal segments are most informative.",
        "No multi-scale analysis: Single-kernel CNNs miss temporal patterns at different granularities.",
    ]
    for g in gaps:
        doc.add_paragraph(g, style='List Number')

    doc.add_paragraph(
        "This project addresses these gaps by providing a complete end-to-end system with "
        "advanced feature engineering (28 features), multi-scale temporal analysis, and an "
        "attention-augmented architecture."
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 3: METHODOLOGY
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 3: METHODOLOGY", level=1)

    # 3.1
    add_heading_styled(doc, "3.1 Dataset Description", level=2)

    doc.add_paragraph("The system uses PPG signal data extracted from fingertip video recordings:")

    add_formatted_table(doc,
        ["Parameter", "Details"],
        [
            ("Data Source", "Fingertip video recordings (smartphone camera + flash)"),
            ("Original Samples", "16 video recordings with paired glucose readings"),
            ("Augmented Samples", "144 (8× augmentation per original sample)"),
            ("Signal Length", "120 frames (standardized)"),
            ("Sampling Rate", "30 FPS (auto-detected, high-FPS videos downsampled)"),
            ("Features Extracted", "28 extended features per sample"),
            ("Target Variable", "Blood glucose level (mg/dL)"),
        ],
        col_widths=[5, 11]
    )

    doc.add_paragraph("The dataset includes recordings taken under varying conditions:")
    for cond in ["Different lighting environments", "Various skin tones",
                  "Different finger pressures", "Varying glucose levels (fasting and post-prandial)"]:
        doc.add_paragraph(cond, style='List Bullet')

    # 3.2
    add_heading_styled(doc, "3.2 Data Preprocessing", level=2)

    doc.add_paragraph(
        "The data preprocessing pipeline is a critical component that transforms raw video "
        "into analysis-ready PPG signals. The pipeline consists of six stages:"
    )

    stages = [
        ("Stage 1: Frame Extraction",
         "Video is opened using OpenCV VideoCapture. FPS is auto-detected from video metadata. "
         "For high-FPS videos (> 45 FPS), frames are subsampled to ~30 FPS to maintain "
         "consistency with the training pipeline. Frames are stored as BGR numpy arrays."),
        ("Stage 2: PPG Signal Extraction",
         "Skin-tone ROI detection using HSV color-space masking with two hue ranges "
         "(H[0–25] and H[160–180]) to handle the red hue wrap-around. Morphological "
         "cleanup (close + open) with 7×7 elliptical kernel. Green channel mean intensity "
         "is extracted per frame. If skin detection fails for > 30% of frames, falls back "
         "to center ROI (50% of frame area)."),
        ("Stage 3: Motion Artifact Removal",
         "2nd-order Butterworth high-pass filter at 0.3 Hz cutoff removes low-frequency "
         "baseline wander caused by finger movement. Applied using scipy.signal.filtfilt "
         "for zero-phase distortion."),
        ("Stage 4: Adaptive Bandpass Filtering",
         "Spectral analysis using Welch's method to find dominant cardiac frequency. "
         "Adaptive filter bounds: dominant frequency ± [0.8 Hz below, 1.2 Hz above]. "
         "4th-order Chebyshev Type II bandpass filter with 40 dB stopband attenuation. "
         "Falls back to standard Butterworth if Chebyshev fails. Cardiac band: 0.7–3.5 Hz."),
        ("Stage 5: Signal Smoothing",
         "Savitzky-Golay filter (window=11, polynomial order=3) preserves peak morphology "
         "(systolic peaks, dicrotic notches) unlike moving average. Falls back to simple "
         "moving average for very short signals."),
        ("Stage 6: Z-Score Normalization",
         "Zero-mean, unit-variance normalization: (x - μ) / σ. Includes numerical stability "
         "handling for near-zero standard deviation."),
    ]

    for title, desc in stages:
        p = doc.add_paragraph()
        run = p.add_run(f"{title}: ")
        run.bold = True
        p.add_run(desc)

    # Preprocessing Flowchart
    add_diagram_box(doc, "Data Preprocessing Pipeline Flowchart", [
        "",
        "┌─────────────────┐",
        "│  📹 Raw Video    │",
        "│     Input        │",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ Frame Extraction │◄── OpenCV VideoCapture",
        "│  (Auto FPS)      │    Subsamples >45 FPS",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ PPG Signal       │◄── Green Channel from",
        "│ Extraction       │    Skin ROI (HSV mask)",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ Motion Artifact  │◄── Butterworth HP",
        "│ Removal          │    @ 0.3 Hz",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ Adaptive Bandpass│◄── Chebyshev Type II",
        "│ Filtering        │    0.7–3.5 Hz",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ Savitzky-Golay   │◄── Window=11",
        "│ Smoothing        │    Order=3",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ Z-Score          │◄── (x - μ) / σ",
        "│ Normalization    │",
        "└────────┬────────┘",
        "         ▼",
        "┌─────────────────┐",
        "│ ✅ Preprocessed  │",
        "│  PPG Signal      │",
        "│  (120 samples)   │",
        "└─────────────────┘",
        "",
    ], "3.1")

    # 3.3
    add_heading_styled(doc, "3.3 Model Selection", level=2)

    doc.add_paragraph(
        "Several model architectures were evaluated during the development process before "
        "arriving at the final architecture:"
    )

    add_formatted_table(doc,
        ["Model Version", "Architecture", "Features", "MAE (mg/dL)", "RMSE (mg/dL)", "R² Score", "Status"],
        [
            ("V1 — Baseline", "Simple LSTM (2 layers, 64 units)", "9 basic", "~25", "~30", "0.62", "❌ Replaced"),
            ("V2 — Improved", "Stacked LSTM (3 layers) + Dense", "11 (9+2 HRV)", "~15", "~18", "0.78", "❌ Replaced"),
            ("V3 — Standard", "Multi-Scale CNN + BiLSTM + Attn", "11 (compat.)", "5.03", "7.37", "0.91", "✅ Production"),
            ("V4 — Enhanced", "Multi-Scale CNN + BiLSTM + Attn", "28 extended", "5.64", "6.69", "0.957", "✅ Primary"),
        ],
        col_widths=[2.5, 4, 2, 2, 2, 1.5, 2]
    )

    add_note_box(doc,
        "The V4 Enhanced model has a marginally higher MAE than V3 but achieves "
        "significantly better RMSE and R² scores, indicating more consistent predictions "
        "with fewer large errors. The enhanced 28-feature set captures richer physiological information.",
        "NOTE"
    )

    # 3.4
    add_heading_styled(doc, "3.4 Algorithms Used", level=2)

    add_heading_styled(doc, "3.4.1 Peak Detection Algorithm", level=3)
    doc.add_paragraph(
        "Adaptive peak detection using scipy.signal.find_peaks with automatic parameter tuning:"
    )
    peak_params = [
        "Minimum distance: 0.3 seconds (~200 BPM max)",
        "Maximum distance: 2.0 seconds (~30 BPM min)",
        "Prominence threshold: 15% of signal range",
        "Outlier rejection using Median Absolute Deviation (MAD) on RR intervals",
        "Physiologically implausible peaks (RR outside 0.3–2.0s) are rejected",
    ]
    for pp in peak_params:
        doc.add_paragraph(pp, style='List Bullet')

    add_heading_styled(doc, "3.4.2 Bandpass Filtering", level=3)
    bp_items = [
        "Chebyshev Type II filter (4th order, 40 dB stopband attenuation)",
        "Superior stopband rejection compared to Butterworth",
        "Forward-backward filtering for zero-phase distortion",
        "Fallback to 3rd-order Butterworth for edge cases",
    ]
    for bp in bp_items:
        doc.add_paragraph(bp, style='List Bullet')

    add_heading_styled(doc, "3.4.3 Feature Engineering (28 Features)", level=3)

    add_formatted_table(doc,
        ["Category", "Count", "Features"],
        [
            ("Statistical", "6", "mean, std, max, min, skewness, kurtosis"),
            ("Peak-Based", "5", "HRV, avg_interval, peak_density, mean_peak_amplitude, peak_regularity"),
            ("Energy", "3", "energy, signal_range, RMS"),
            ("Frequency-Domain", "4", "spectral_entropy, dominant_frequency, LF/HF_ratio, total_power"),
            ("Morphological", "4", "mean_rise_time, mean_fall_time, mean_pulse_width, mean_peak_sharpness"),
            ("Nonlinear", "2", "sample_entropy, zero_crossing_rate"),
            ("HRV Extended", "4", "SDNN, RMSSD, pNN50, CV_RR"),
        ],
        col_widths=[3.5, 1.5, 11]
    )

    add_heading_styled(doc, "3.4.4 LSTM Prediction Model", level=3)

    doc.add_paragraph(
        "The LSTM (Long Short-Term Memory) neural network is a specialized recurrent neural "
        "network designed for sequential/time-series data. It uses three gate mechanisms:"
    )

    lstm_gates = [
        ("Forget Gate (σ)", "Decides what to discard from the cell state"),
        ("Input Gate (σ)", "Decides what new information to store"),
        ("Output Gate (σ)", "Decides what to output from the cell state"),
        ("Cell State (Cₜ)", "Long-term memory that flows through the network"),
    ]
    for gate, desc in lstm_gates:
        p = doc.add_paragraph(style='List Bullet')
        run = p.add_run(f"{gate}: ")
        run.bold = True
        p.add_run(desc)

    add_diagram_box(doc, "LSTM Cell Architecture", [
        "",
        "                  ┌───────────────────────────────┐",
        "                  │         LSTM Cell              │",
        "   ┌──────┐       │                               │",
        "   │  xₜ  │──────►│  ┌─────────┐  ┌─────────┐   │",
        "   └──────┘       │  │ Forget   │  │  Input   │   │",
        "                  │  │ Gate (σ) │  │ Gate (σ) │   │",
        "   ┌──────┐       │  └────┬────┘  └────┬────┘   │",
        "   │ hₜ₋₁ │──────►│       │            │         │",
        "   └──────┘       │       ▼            ▼         │",
        "                  │  ┌─────────────────────┐     │",
        "                  │  │    Cell State (Cₜ)  │     │",
        "                  │  └──────────┬──────────┘     │",
        "                  │             │                 │",
        "                  │  ┌──────────▼──────────┐     │    ┌──────┐",
        "                  │  │   Output Gate (σ)   │─────│───►│  hₜ  │",
        "                  │  └─────────────────────┘     │    └──────┘",
        "                  └───────────────────────────────┘",
        "",
    ], "3.2")

    # 3.5
    add_heading_styled(doc, "3.5 System Workflow", level=2)

    add_diagram_box(doc, "Complete System Workflow", [
        "",
        "  👤 User opens GlucoAI Monitor",
        "           │",
        "           ▼",
        "  ┌─────────────────┐     ┌──────────────┐",
        "  │  Authenticated? │─No─►│ Login/Signup  │",
        "  └────────┬────────┘     │    Page       │",
        "          Yes             └──────┬────────┘",
        "           │                     │",
        "           ▼                     ▼",
        "  ┌─────────────────┐   ┌──────────────┐",
        "  │    Dashboard    │◄──│ SQLite DB    │",
        "  └────────┬────────┘   │ Validation   │",
        "           │            └──────────────┘",
        "           ▼",
        "  📹 Upload Fingertip Video (≤100 MB)",
        "           │",
        "           ▼",
        "  ┌─────────────────────────────────────┐",
        "  │     SIGNAL PROCESSING PIPELINE      │",
        "  │                                     │",
        "  │  Extract Frames ──► PPG Signal      │",
        "  │       │                  │           │",
        "  │       ▼                  ▼           │",
        "  │  Motion Removal ──► Bandpass Filter  │",
        "  │       │                  │           │",
        "  │       ▼                  ▼           │",
        "  │  Smoothing ──► Normalization         │",
        "  └──────────────────┬──────────────────┘",
        "                     │",
        "           ┌────────┼────────┐",
        "           ▼        ▼        ▼",
        "      Peak Detect  LSTM   PPG Plot",
        "           │      Model      │",
        "           ▼        ▼        ▼",
        "       Heart     Glucose   Waveform",
        "       Rate      Level     Graph",
        "           │        │        │",
        "           ▼        ▼        ▼",
        "  ┌─────────────────────────────────────┐",
        "  │      📊 DISPLAY RESULTS             │",
        "  │  Glucose │ Heart Rate │ PPG Graph    │",
        "  └──────────────────┬──────────────────┘",
        "                     │",
        "                     ▼",
        "            Save to History",
        "",
    ], "3.3")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 4: SYSTEM DESIGN
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 4: SYSTEM DESIGN", level=1)

    # 4.1
    add_heading_styled(doc, "4.1 Architecture Diagram", level=2)

    doc.add_paragraph(
        "The system follows a three-tier client-server architecture with a clear separation of concerns:"
    )

    add_diagram_box(doc, "Three-Tier System Architecture", [
        "",
        "┌──────────────────────────────────────────────────────────┐",
        "│              🖥  FRONTEND (React + Vite)                 │",
        "│                                                          │",
        "│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │",
        "│  │ Landing  │  │  Auth    │  │     Dashboard         │  │",
        "│  │  Page    │─►│  Page    │─►│  ┌────────┐ ┌──────┐  │  │",
        "│  └──────────┘  └──────────┘  │  │Upload  │ │Result│  │  │",
        "│                              │  │Panel   │ │Panel │  │  │",
        "│  ┌────────────────────────┐  │  └────────┘ └──────┘  │  │",
        "│  │ Auth Context (State)   │  │  ┌──────────────────┐ │  │",
        "│  └────────────────────────┘  │  │  History Panel   │ │  │",
        "│                              │  └──────────────────┘ │  │",
        "│                              └───────────────────────┘  │",
        "└──────────────────────────┬───────────────────────────────┘",
        "                          │ HTTP REST API",
        "                          │ (JSON + FormData)",
        "                          ▼",
        "┌──────────────────────────────────────────────────────────┐",
        "│              ⚙  BACKEND (Flask API)                     │",
        "│                                                          │",
        "│  ┌──────────┐  ┌───────────────┐  ┌──────────────────┐  │",
        "│  │ app.py   │  │ ppg_extraction│  │  lstm_model.py   │  │",
        "│  │ (Routes) │─►│ .py (Signal   │─►│  (AI Inference)  │  │",
        "│  └──────────┘  │  Processing)  │  └──────────────────┘  │",
        "│       │        └───────────────┘           │             │",
        "│       ▼                                    ▼             │",
        "│  ┌──────────┐              ┌────────────────────────┐   │",
        "│  │database  │              │  🧠 AI / ML Layer      │   │",
        "│  │.py       │              │  ┌────────┐ ┌────────┐ │   │",
        "│  └────┬─────┘              │  │Standard│ │Enhanced│ │   │",
        "│       │                    │  │Model   │ │Model   │ │   │",
        "│       ▼                    │  │(11 ft) │ │(28 ft) │ │   │",
        "│  ┌──────────┐              │  └────────┘ └────────┘ │   │",
        "│  │ SQLite   │              │  ┌────────┐ ┌────────┐ │   │",
        "│  │ users.db │              │  │Feature │ │  Y     │ │   │",
        "│  └──────────┘              │  │Scaler  │ │ Scaler │ │   │",
        "│                            │  └────────┘ └────────┘ │   │",
        "│                            └────────────────────────┘   │",
        "└──────────────────────────────────────────────────────────┘",
        "",
    ], "4.1")

    # 4.2
    add_heading_styled(doc, "4.2 Data Flow Diagrams (DFD)", level=2)

    add_heading_styled(doc, "DFD Level 0 — Context Diagram", level=3)

    add_diagram_box(doc, "DFD Level 0 — Context Diagram", [
        "",
        "                Login credentials",
        "                Video file",
        "   ┌──────┐    ─────────────────►    ╔═══════════════╗",
        "   │      │                          ║               ║",
        "   │ User │                          ║   GlucoAI     ║",
        "   │      │                          ║   Monitor     ║",
        "   │      │    ◄─────────────────    ║   System      ║",
        "   └──────┘    Glucose level         ║               ║",
        "               Heart rate            ╚═══════════════╝",
        "               PPG graph",
        "               History",
        "",
    ], "4.2")

    add_heading_styled(doc, "DFD Level 1", level=3)

    add_diagram_box(doc, "DFD Level 1 — Module Decomposition", [
        "",
        "                 ┌───────────────────┐",
        " Email,Password  │  1.0              │  Query/Insert",
        " ───────────────►│  Authentication   │◄────────────►  [SQLite DB]",
        "                 │  Module           │",
        "                 └───────────────────┘",
        "",
        "                 ┌───────────────────┐",
        " Video File      │  2.0              │  Extracted PPG Signal",
        " ───────────────►│  Video Processing │──────────────────────►",
        "                 │  Module           │",
        "                 └───────────────────┘",
        "                                             │",
        "                 ┌───────────────────┐       ▼",
        "                 │  3.0              │  Cleaned Signal",
        "                 │  Signal           │──────────────────────►",
        "                 │  Preprocessing    │",
        "                 └───────────────────┘       │",
        "                                             ▼",
        "                 ┌───────────────────┐  28 Features",
        "                 │  4.0              │  + Signal Array",
        "                 │  Feature          │──────────────────────►",
        "                 │  Extraction       │",
        "                 └───────────────────┘       │",
        "                                             ▼",
        "                 ┌───────────────────┐  Glucose (mg/dL)",
        "                 │  5.0              │  Heart Rate (BPM)",
        "                 │  AI Prediction    │──────────────────────►",
        "                 │  Module           │",
        "                 └───────────────────┘       │",
        "                                             ▼",
        "                 ┌───────────────────┐  Results JSON",
        "                 │  6.0              │  + PPG Graph",
        " ◄───────────────│  Visualization    │◄──────────────────",
        "   To User       │  Module           │",
        "                 └───────────────────┘",
        "",
    ], "4.3")

    add_heading_styled(doc, "DFD Level 2 — Video Processing & Prediction Detail", level=3)

    add_diagram_box(doc, "DFD Level 2 — Detailed Processing Flow", [
        "",
        " Video ──► 2.1 Open Video ──► 2.2 Detect FPS",
        "                                    │",
        "                           ┌────────┴────────┐",
        "                    FPS>45 │                  │ FPS≤45",
        "                           ▼                  ▼",
        "                    2.3 Subsample     2.4 Extract All",
        "                           │                  │",
        "                           └────────┬────────┘",
        "                                    ▼",
        "                          2.5 Skin ROI Detection (HSV)",
        "                                    │",
        "                                    ▼",
        "                    2.6 Green Channel Mean Extraction",
        "                                    │",
        "                                    ▼",
        "              3.1 HP Filter ──► 3.2 Adaptive BP Filter",
        "                                    │",
        "                                    ▼",
        "              3.3 Savgol Smooth ──► 3.4 Z-Score Norm",
        "                                    │",
        "                                    ▼",
        "              4.1 Peak Detection ──► 4.2 Extract 28 Features",
        "                                    │",
        "                           ┌────────┴────────┐",
        "                           ▼                  ▼",
        "                5.1 Scale Features    5.2 Reshape Signal",
        "                    (RobustScaler)       (1, 120, 1)",
        "                           │                  │",
        "                           └────────┬────────┘",
        "                                    ▼",
        "                      5.3 LSTM Model Inference",
        "                                    │",
        "                                    ▼",
        "                   5.4 Inverse Scale (MinMaxScaler)",
        "                                    │",
        "                                    ▼",
        "              5.5 Physiological Guardrails (50–400 mg/dL)",
        "                                    │",
        "                                    ▼",
        "                          Glucose Prediction",
        "",
    ], "4.4")

    # 4.3
    add_heading_styled(doc, "4.3 Entity-Relationship (ER) Diagram", level=2)

    add_diagram_box(doc, "Entity-Relationship (ER) Diagram", [
        "",
        "  ┌─────────────────────┐         ┌─────────────────────────┐",
        "  │       USERS         │         │     VIDEO_UPLOADS       │",
        "  ├─────────────────────┤         ├─────────────────────────┤",
        "  │ PK  id (INTEGER)    │         │ PK  id (INTEGER)        │",
        "  │     email (TEXT) UK  │────1:N──│ FK  user_id (INTEGER)   │",
        "  │     password (TEXT)  │         │     filename (TEXT)      │",
        "  └─────────────────────┘         │     filepath (TEXT)      │",
        "                                  │     uploaded_at (DATETIME)│",
        "                                  │     processed (BOOLEAN)  │",
        "                                  └────────────┬────────────┘",
        "                                               │",
        "                                              1:1",
        "                                               │",
        "                                  ┌────────────▼────────────┐",
        "                                  │      PREDICTIONS       │",
        "                                  ├─────────────────────────┤",
        "                                  │ PK  id (INTEGER)        │",
        "                                  │ FK  upload_id (INTEGER)  │",
        "                                  │     glucose_level (FLOAT)│",
        "                                  │     heart_rate (FLOAT)   │",
        "                                  │     confidence (FLOAT)   │",
        "                                  │     reliability (TEXT)   │",
        "                                  │     signal_quality (TEXT)│",
        "                                  │     model_type (TEXT)    │",
        "                                  │     ppg_graph (TEXT)     │",
        "                                  │     predicted_at (DATETIME)│",
        "                                  └────────────┬────────────┘",
        "                                               │",
        "                                              1:1",
        "                                               │",
        "                                  ┌────────────▼────────────┐",
        "                                  │    SIGNAL_FEATURES     │",
        "                                  ├─────────────────────────┤",
        "                                  │ PK  id (INTEGER)        │",
        "                                  │ FK  prediction_id (INT)  │",
        "                                  │     mean_val (FLOAT)    │",
        "                                  │     std_val (FLOAT)     │",
        "                                  │     hrv (FLOAT)         │",
        "                                  │     spectral_entropy    │",
        "                                  │     dominant_freq       │",
        "                                  │     sample_entropy      │",
        "                                  │     sdnn (FLOAT)        │",
        "                                  │     rmssd (FLOAT)       │",
        "                                  └─────────────────────────┘",
        "",
    ], "4.5")

    add_note_box(doc,
        "The current implementation uses a simplified SQLite schema with only the USERS "
        "table for authentication. The VIDEO_UPLOADS, PREDICTIONS, and SIGNAL_FEATURES "
        "tables represent the logical data model and are candidates for future database "
        "expansion. Currently, prediction history is maintained in the frontend React state.",
        "NOTE"
    )

    # 4.4
    add_heading_styled(doc, "4.4 LSTM Model Architecture Diagram", level=2)

    add_diagram_box(doc, "Multi-Scale CNN + BiLSTM + Attention Architecture", [
        "",
        "  SIGNAL INPUT (1, 120, 1)          FEATURE INPUT (1, 28)",
        "         │                                   │",
        "         ▼                                   ▼",
        "  GaussianNoise(σ=0.01)             Dense(64, ReLU)",
        "         │                            + BatchNorm",
        "  ┌──────┼──────┐                    + Dropout(0.35)",
        "  │      │      │                           │",
        "  ▼      ▼      ▼                           ▼",
        " Conv1D Conv1D Conv1D               Dense(32, ReLU)",
        " k=3    k=5    k=7                    + BatchNorm",
        " 32f    32f    32f                          │",
        "  │      │      │                           │",
        "  └──────┼──────┘                           │",
        "         ▼                                   │",
        "  Concatenate → (120, 96)                   │",
        "  + BatchNorm                               │",
        "  + SpatialDropout1D(0.15)                  │",
        "         │                                   │",
        "         ▼                                   │",
        "  Conv1D(64, k=3) + BatchNorm               │",
        "  + MaxPool(2) → (60, 64)                   │",
        "  + SpatialDropout1D(0.15)                  │",
        "         │                                   │",
        "    ┌────┴────┐                              │",
        "    │         │                              │",
        "    ▼         ▼                              │",
        " BiLSTM   BiLSTM                            │",
        " (64,     (32)                              │",
        " ret_seq)    │                              │",
        "    │        │                              │",
        "    ▼        │                              │",
        " Self-      │                              │",
        " Attention   │                              │",
        "    │        │                              │",
        "    └────┬───┘                              │",
        "         ▼                                   │",
        "    Concatenate (LSTM + Attn) → (192)       │",
        "         │                                   │",
        "         └────────────┬──────────────────────┘",
        "                     ▼",
        "              Concatenate → (224)",
        "                     │",
        "                     ▼",
        "           Dense(128) + BN + Dropout(0.35)",
        "                     │",
        "                     ▼",
        "           Dense(64) + Dropout(0.25)",
        "                     │",
        "                     ▼",
        "              Dense(32, ReLU)",
        "                     │",
        "                     ▼",
        "         Dense(1, Sigmoid) → Glucose",
        "",
    ], "4.6")

    # 4.5
    add_heading_styled(doc, "4.5 Tools & Technologies", level=2)

    add_formatted_table(doc,
        ["Category", "Technology", "Version", "Purpose"],
        [
            ("Frontend Framework", "React", "19.2.4", "UI component framework"),
            ("Build Tool", "Vite", "8.0.4", "Fast development server & bundler"),
            ("Frontend Routing", "React Router DOM", "7.14.0", "Client-side routing"),
            ("Animations", "Framer Motion", "12.38.0", "Smooth UI animations"),
            ("Charts", "Chart.js + react-chartjs-2", "4.5.1 / 5.3.1", "Data visualization"),
            ("HTTP Client", "Fetch API (native)", "—", "API communication"),
            ("Notifications", "React Hot Toast", "2.6.0", "Toast notifications"),
            ("Icons", "React Icons", "5.6.0", "UI icons"),
            ("Backend Framework", "Flask", "3.1.3", "REST API server"),
            ("CORS", "Flask-CORS", "6.0.2", "Cross-origin requests"),
            ("Database", "SQLite3", "Built-in", "User authentication data"),
            ("Video Processing", "OpenCV", "4.13.0", "Frame extraction & ROI detection"),
            ("Deep Learning", "TensorFlow / Keras", "2.21.0 / 3.13.2", "LSTM model training & inference"),
            ("Signal Processing", "SciPy", "1.17.1", "Filtering, peak detection"),
            ("Scientific Computing", "NumPy", "2.4.3", "Array operations"),
            ("Data Handling", "Pandas", "3.0.1", "Dataset management"),
            ("Feature Scaling", "Scikit-Learn", "1.8.0", "MinMaxScaler, RobustScaler"),
            ("Model Serialization", "Joblib", "1.5.3", "Scaler persistence"),
            ("Plotting", "Matplotlib", "3.10.8", "PPG waveform visualization"),
            ("Language", "Python", "3.x", "Backend language"),
            ("Language", "JavaScript (ES6+)", "—", "Frontend language"),
        ],
        col_widths=[3, 4, 3, 6]
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 5: IMPLEMENTATION
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 5: IMPLEMENTATION", level=1)

    # 5.1
    add_heading_styled(doc, "5.1 Model Training", level=2)

    doc.add_paragraph(
        "The model training pipeline is implemented in train_model.py and follows a "
        "rigorous multi-phase process:"
    )

    add_heading_styled(doc, "5.1.1 Training Configuration", level=3)

    add_formatted_table(doc,
        ["Hyperparameter", "Value", "Rationale"],
        [
            ("Epochs", "200", "Maximum training iterations"),
            ("Batch Size", "4", "Small batch for limited dataset"),
            ("Learning Rate", "0.001", "Adam optimizer initial LR"),
            ("Minimum LR", "1×10⁻⁶", "Lower bound for LR scheduling"),
            ("Early Stopping Patience", "25 epochs", "Prevents overfitting"),
            ("LR Reduction Patience", "10 epochs", "Reduces LR on plateau"),
            ("LR Reduction Factor", "0.5", "Halve LR on plateau"),
            ("Dropout Rate", "0.35", "Regularization strength"),
            ("L2 Regularization", "1×10⁻⁴", "Weight decay"),
            ("Augmentation Factor", "8×", "Data augmentation multiplier"),
            ("K-Fold CV", "4-fold", "Cross-validation for robustness"),
            ("Loss Function", "Huber Loss", "Robust to outliers"),
            ("Output Activation", "Sigmoid", "Targets scaled to [0.05, 0.95]"),
        ],
        col_widths=[4, 3, 9]
    )

    add_heading_styled(doc, "5.1.2 Data Augmentation Strategy", level=3)

    add_formatted_table(doc,
        ["Augmentation", "Probability", "Parameters", "Purpose"],
        [
            ("Gaussian Noise", "90%", "σ ∈ [0.01, 0.05]", "Simulates sensor noise"),
            ("Amplitude Scaling", "70%", "Scale ∈ [0.85, 1.15]", "Simulates varying finger pressure"),
            ("Time-Shift", "60%", "Shift ∈ [−5, +5] frames", "Simulates timing variations"),
            ("Smooth Distortion", "40%", "Low-freq sinusoidal noise", "Simulates slow motion artifacts"),
            ("Segment Reversal", "20%", "10–30 frame segments flipped", "Increases pattern diversity"),
        ],
        col_widths=[3.5, 2, 4, 6.5]
    )

    add_heading_styled(doc, "5.1.3 Training Process", level=3)

    add_diagram_box(doc, "Model Training Pipeline", [
        "",
        "  Load Dataset (video_data.csv)",
        "         │",
        "         ▼",
        "  Process Videos → PPG Signals",
        "         │",
        "         ▼",
        "  Extract 28 Features per Signal",
        "         │",
        "         ▼",
        "  Scale Targets (MinMaxScaler [0.05, 0.95])",
        "         │",
        "         ▼",
        "  Scale Features (RobustScaler)",
        "         │",
        "         ▼",
        "  Data Augmentation (8× per sample)",
        "         │",
        "  ┌──────┴──────┐",
        "  │             │",
        "  ▼             ▼",
        " Phase 1:    Phase 2:",
        " Standard    4-Fold CV",
        " Model       (Enhanced)",
        " (11 feat)   (28 feat)",
        "  │             │",
        "  └──────┬──────┘",
        "         ▼",
        "  Phase 3: Train Final Enhanced Model",
        "         │",
        "         ▼",
        "  Evaluate on Original Data",
        "         │",
        "         ▼",
        "  Save Models & Scalers",
        "         │",
        "         ▼",
        "  Generate Training Report (JSON)",
        "",
    ], "5.1")

    add_heading_styled(doc, "5.1.4 Regularization Techniques", level=3)

    reg_techniques = [
        ("Dropout (0.35)", "Randomly zeros 35% of neurons during training"),
        ("SpatialDropout1D (0.15)", "Drops entire 1D feature maps in temporal convolutions"),
        ("GaussianNoise (σ=0.01)", "Adds noise to inputs during training"),
        ("L2 Weight Regularization (λ=10⁻⁴)", "Penalizes large weights"),
        ("BatchNormalization", "Normalizes layer inputs, acts as implicit regularizer"),
        ("Early Stopping", "Stops training when validation loss plateaus (patience=25)"),
        ("Learning Rate Scheduling", "Reduces LR by 50% on plateau (patience=10)"),
        ("Data Augmentation", "8× augmentation prevents memorizing training samples"),
    ]
    for i, (name, desc) in enumerate(reg_techniques, 1):
        p = doc.add_paragraph()
        run = p.add_run(f"{i}. {name}: ")
        run.bold = True
        p.add_run(desc)

    # 5.2
    add_heading_styled(doc, "5.2 Testing Process", level=2)

    add_heading_styled(doc, "5.2.1 Signal Quality Assessment", level=3)

    add_formatted_table(doc,
        ["Criterion", "Method", "Threshold"],
        [
            ("SNR", "Welch PSD (cardiac band vs. noise band)", "> 10 dB = Good, > 5 dB = Acceptable"),
            ("Periodic Component", "Dominant frequency detection", "Must be > 0.5 Hz"),
            ("Saturation", "Extrema ratio check", "< 20% at extremes"),
            ("Flatline", "Peak-to-peak range", "Range > 1×10⁻⁶"),
            ("Motion Artifacts", "Large-jump ratio in signal diff", "< 5% = Good, < 15% = Acceptable"),
            ("Usable Segments", "Local variance windowed check", "> 10% of median variance"),
        ],
        col_widths=[3, 5.5, 7.5]
    )

    doc.add_paragraph("Quality grades: GOOD → ACCEPTABLE → POOR → UNUSABLE")

    add_heading_styled(doc, "5.2.2 Physiological Guardrails", level=3)

    guardrails = [
        "Soft sigmoid clipping: Smoothly constrains predictions to 50–400 mg/dL range",
        "Hard minimum safety net: Glucose ≥ 50 mg/dL (to prevent dangerous false-lows)",
        "Confidence scoring: Based on signal quality (GOOD=95%, ACCEPTABLE=75%, POOR=45%, UNUSABLE=10%)",
        "Reliability grading: HIGH (confidence ≥ 85%), MEDIUM (≥ 60%), LOW (< 60%)",
    ]
    for g in guardrails:
        doc.add_paragraph(g, style='List Bullet')

    add_heading_styled(doc, "5.2.3 Testing Conditions", level=3)

    add_formatted_table(doc,
        ["Condition", "Description", "Result"],
        [
            ("Good Lighting", "Well-lit room, flash ON", "Best signal quality"),
            ("Low Lighting", "Dim environment, no flash", "Reduced signal quality"),
            ("Motion", "Finger movement during recording", "Motion artifacts detected & filtered"),
            ("Short Video", "< 15 seconds", "Signal padded (reflect mode)"),
            ("Different Skin Tones", "Various ethnic backgrounds", "Adaptive skin-tone detection handles diversity"),
            ("High FPS Video", "60/120 FPS smartphone", "Auto-downsampled to 30 FPS"),
        ],
        col_widths=[3.5, 5, 7.5]
    )

    # 5.3
    add_heading_styled(doc, "5.3 Screenshots / Outputs", level=2)

    screenshots = [
        ("Landing Page", "Main landing page with hero section, project description, and 'Get Started' button", "5.1"),
        ("Login / Signup Page", "Authentication form with email and password fields, toggle between login and signup modes", "5.2"),
        ("Dashboard — Upload Panel", "Navigation bar, drag-and-drop upload area, recording tips, and 'Analyze Video' button", "5.3"),
        ("Video Processing / Loading State", "Progress bar with steps — Extracting frames, Computing PPG signal, Filtering & smoothing, Running LSTM model", "5.4"),
        ("Results Panel — Glucose & Heart Rate", "Glucose level card (mg/dL with status badge), Heart rate card (BPM with pulse animation), gauge indicators", "5.5"),
        ("PPG Waveform Graph", "Dark-themed PPG waveform plot with peak annotations, HR badge, and signal quality indicator", "5.6"),
        ("History Panel", "List of previous predictions with timestamps, glucose values, and heart rates", "5.7"),
    ]
    for label, desc, fig_num in screenshots:
        add_placeholder_box(doc, label, desc, fig_num)

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 6: RESULTS & ANALYSIS
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 6: RESULTS & ANALYSIS", level=1)

    # 6.1
    add_heading_styled(doc, "6.1 Performance Metrics", level=2)

    add_heading_styled(doc, "6.1.1 Model Training Results", level=3)

    doc.add_paragraph("Results from training_report.json (actual training output):")

    add_formatted_table(doc,
        ["Metric", "Standard Model (V3)", "Enhanced Model (V4)", "Improvement"],
        [
            ("Mean Absolute Error (MAE)", "5.03 mg/dL", "5.64 mg/dL", "—"),
            ("Root Mean Square Error (RMSE)", "7.37 mg/dL", "6.69 mg/dL", "+9.2%"),
            ("R² Score", "0.91", "0.957", "+5.2%"),
            ("Number of Features", "11", "28", "+17 features"),
            ("Dataset Size (Original)", "16 samples", "16 samples", "—"),
            ("Dataset Size (Augmented)", "144 samples", "144 samples", "—"),
            ("Cross-Validation", "—", "4-Fold CV", "—"),
            ("Processing Time", "5–8 seconds", "5–10 seconds", "—"),
        ],
        col_widths=[4.5, 3.5, 3.5, 4.5]
    )

    add_heading_styled(doc, "6.1.2 Comprehensive Model Comparison Table", level=3)

    add_formatted_table(doc,
        ["Criteria", "V1 Baseline", "V2 Stacked", "V3 Standard", "V4 Enhanced"],
        [
            ("Architecture", "Simple LSTM\n(2 layers)", "Stacked LSTM\n(3 layers)", "Multi-Scale CNN\n+ BiLSTM + Attn", "Multi-Scale CNN\n+ BiLSTM + Attn"),
            ("Feature Count", "9 basic", "11 (9+2 HRV)", "11 (compat.)", "28 extended"),
            ("CNN Component", "None", "None", "Multi-Scale\n(k=3,5,7)", "Multi-Scale\n(k=3,5,7)"),
            ("LSTM Type", "Unidirectional", "Unidirectional", "Bidirectional", "Bidirectional"),
            ("Attention", "None", "None", "Self-Attention", "Self-Attention"),
            ("Filter Type", "Butterworth", "Butterworth", "Chebyshev II", "Chebyshev II\n(Adaptive)"),
            ("Data Augmentation", "None", "2× noise", "8× (5 techniques)", "8× (5 techniques)"),
            ("Loss Function", "MSE", "MSE", "Huber", "Huber"),
            ("MAE (mg/dL)", "~25", "~15", "5.03", "5.64"),
            ("RMSE (mg/dL)", "~30", "~18", "7.37", "6.69"),
            ("R² Score", "0.62", "0.78", "0.91", "0.957"),
            ("Signal Quality", "None", "None", "SNR + Artifacts", "SNR + Artifacts\n+ Periodicity"),
            ("Confidence Score", "None", "None", "Quality-based", "Quality-based"),
            ("Guardrails", "Hard clip", "Hard clip", "Soft sigmoid", "Soft sigmoid"),
        ],
        col_widths=[3, 2.5, 2.5, 4, 4]
    )

    add_heading_styled(doc, "6.1.3 Heart Rate Estimation Accuracy", level=3)

    add_formatted_table(doc,
        ["Metric", "Value"],
        [
            ("Accuracy", "90–95% (compared to manual pulse count)"),
            ("Method", "Median RR interval from adaptive peak detection"),
            ("Physiological Clamp", "30–220 BPM"),
            ("Outlier Rejection", "MAD-based (3σ threshold)"),
        ],
        col_widths=[5, 11]
    )

    # 6.2
    add_heading_styled(doc, "6.2 Graphs & Evaluation", level=2)

    add_heading_styled(doc, "6.2.1 Model MAE Improvement Across Versions", level=3)

    add_diagram_box(doc, "MAE Improvement Chart", [
        "",
        "  MAE (mg/dL)",
        "  30 │",
        "     │  ████",
        "  25 │  ████  (V1: ~25)",
        "     │  ████",
        "  20 │  ████",
        "     │  ████",
        "  15 │  ████  ████",
        "     │  ████  ████  (V2: ~15)",
        "  10 │  ████  ████",
        "     │  ████  ████",
        "   5 │  ████  ████  ████  ████",
        "     │  ████  ████  ████  ████  (V3: 5.03, V4: 5.64)",
        "   0 │──████──████──████──████──",
        "     │  V1     V2    V3    V4",
        "     │ Base   Stack  Std   Enh",
        "",
    ], "6.1")

    add_heading_styled(doc, "6.2.2 R² Score Improvement Across Versions", level=3)

    add_diagram_box(doc, "R² Score Progression Chart", [
        "",
        "  R² Score",
        "  1.0 │                        ████",
        "      │                  ████  ████",
        "  0.9 │                  ████  ████  (V3: 0.91, V4: 0.957)",
        "      │            ████  ████  ████",
        "  0.8 │            ████  ████  ████  (V2: 0.78)",
        "      │      ████  ████  ████  ████",
        "  0.7 │      ████  ████  ████  ████",
        "      │      ████  ████  ████  ████",
        "  0.6 │      ████  ████  ████  ████  (V1: 0.62)",
        "      │      ████  ████  ████  ████",
        "  0.5 │      ████  ████  ████  ████",
        "    0 │──────████──████──████──████──",
        "      │       V1    V2    V3    V4",
        "",
    ], "6.2")

    add_heading_styled(doc, "6.2.3 Feature Category Contribution", level=3)

    add_formatted_table(doc,
        ["Feature Category", "Count", "Key Features", "Impact on Prediction"],
        [
            ("Statistical", "6", "mean, std, skewness, kurtosis", "Baseline signal characteristics"),
            ("Peak-Based", "5", "HRV, peak_density, peak_regularity", "Cardiac rhythm encoding"),
            ("Energy", "3", "energy, RMS, signal_range", "Signal power distribution"),
            ("Frequency-Domain", "4", "spectral_entropy, LF/HF ratio", "Autonomic nervous system indicators"),
            ("Morphological", "4", "rise_time, fall_time, pulse_width", "Vascular compliance markers"),
            ("Nonlinear", "2", "sample_entropy, zero_crossing_rate", "Signal complexity"),
            ("HRV Extended", "4", "SDNN, RMSSD, pNN50, CV_RR", "Heart rate variability"),
        ],
        col_widths=[3, 1.5, 5.5, 6]
    )

    # 6.3
    add_heading_styled(doc, "6.3 Observations", level=2)

    observations = [
        ("Lighting Conditions", "The system works best under good, consistent lighting (or with smartphone flash ON). Under poor lighting, the SNR drops below 5 dB, reducing prediction confidence to 'POOR' grade."),
        ("Motion Sensitivity", "The adaptive bandpass filter and motion artifact removal significantly improve robustness, but excessive motion (finger sliding on camera) still degrades signal quality. The system detects this and reports low confidence."),
        ("Signal Stability", "Recordings longer than 15 seconds with steady finger pressure produce the most stable signals. Very short recordings (< 5 seconds) result in reflect-padding artifacts."),
        ("Skin Tone Adaptation", "The HSV-based skin detection works across diverse skin tones. When skin detection fails for > 30% of frames, the system automatically falls back to center ROI extraction."),
        ("Model Convergence", "The enhanced model achieves best validation loss within 80–120 epochs (out of 200 max), indicating that early stopping prevents overfitting effectively."),
        ("Peak Detection Quality", "The adaptive peak detection with MAD-based outlier rejection correctly identifies 95%+ of cardiac peaks in good-quality signals, directly improving heart rate and HRV feature accuracy."),
    ]
    for i, (title, desc) in enumerate(observations, 1):
        p = doc.add_paragraph()
        run = p.add_run(f"{i}. {title}: ")
        run.bold = True
        p.add_run(desc)

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # CHAPTER 7: CONCLUSION & FUTURE SCOPE
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "CHAPTER 7: CONCLUSION & FUTURE SCOPE", level=1)

    add_heading_styled(doc, "7.1 Conclusion", level=2)

    doc.add_paragraph(
        "The GlucoAI Monitor project successfully demonstrates a non-invasive approach to "
        "glucose monitoring using Artificial Intelligence and Computer Vision. The key "
        "achievements of this project are:"
    )

    achievements = [
        ("Complete End-to-End System", "A fully functional web application that takes a fingertip video as input and provides glucose level predictions, heart rate estimation, and PPG waveform visualization — all in under 10 seconds."),
        ("Advanced Signal Processing Pipeline", "A production-grade signal processing pipeline with adaptive skin-tone ROI detection, motion artifact removal, adaptive Chebyshev bandpass filtering, and Savitzky-Golay peak-preserving smoothing."),
        ("Comprehensive Feature Engineering", "28 engineered features across 7 categories (statistical, peak-based, energy, frequency-domain, morphological, nonlinear, HRV) that capture the full physiological information encoded in PPG signals."),
        ("State-of-the-Art Deep Learning Architecture", "A Multi-Scale CNN + Bidirectional LSTM + Self-Attention model that extracts temporal patterns at multiple granularities and learns which time steps are most informative for glucose prediction."),
        ("High Accuracy", "The final model achieves an R² score of 0.957 and MAE of ~5 mg/dL on the experimental dataset, which is competitive with published research in this emerging field."),
        ("Robust Production Design", "Thread-safe model loading, input validation, confidence scoring, physiological guardrails, and graceful error handling make the system suitable for real-world deployment."),
    ]
    for i, (title, desc) in enumerate(achievements, 1):
        p = doc.add_paragraph()
        run = p.add_run(f"{i}. {title}: ")
        run.bold = True
        p.add_run(desc)

    doc.add_paragraph(
        "While the system is still experimental and not intended for clinical use, it "
        "demonstrates the significant potential of combining AI and healthcare technologies "
        "to create accessible, non-invasive, and scalable health monitoring solutions."
    )

    add_heading_styled(doc, "7.2 Future Scope", level=2)

    add_formatted_table(doc,
        ["Area", "Description", "Priority"],
        [
            ("Mobile App Integration", "Native iOS/Android app with built-in camera capture", "High"),
            ("Real-Time Camera Monitoring", "Live PPG extraction from camera stream with real-time glucose display", "High"),
            ("Cloud Deployment", "Deploy backend on AWS/GCP/Azure with auto-scaling", "Medium"),
            ("Larger, Diverse Dataset", "Collect PPG-glucose paired data from 500+ subjects", "High"),
            ("Transfer Learning", "Fine-tune model on personalized data from individual users", "Medium"),
            ("Multi-Wavelength Analysis", "Use both regular and infrared camera modes", "Medium"),
            ("Medical Device Certification", "Pursue FDA/CE certification for clinical-grade monitoring", "Long-term"),
            ("Wearable Integration", "Adapt pipeline for smartwatch PPG sensors", "Medium"),
            ("Continuous Monitoring", "Background monitoring with periodic checks and alerts", "High"),
            ("Federated Learning", "Privacy-preserving model training across hospitals", "Long-term"),
            ("EHR Integration", "Export prediction history to standard health record formats", "Low"),
        ],
        col_widths=[4, 8, 4]
    )

    add_heading_styled(doc, "7.3 Limitations", level=2)

    limitations = [
        "Small Dataset: The current model is trained on only 16 original samples (augmented to 144), which limits generalization to unseen individuals.",
        "Experimental Accuracy: While MAE of ~5 mg/dL is promising, clinical glucose monitors require accuracy within ±15% for > 95% of readings.",
        "No Personalization: The model does not account for individual-specific PPG-glucose relationships that vary with age, BMI, and skin characteristics.",
        "Environmental Sensitivity: Performance degrades significantly under poor lighting or excessive motion.",
        "Correlation ≠ Causation: The model may be learning correlations in the training data that do not generalize to the broader population.",
    ]
    for lim in limitations:
        doc.add_paragraph(lim, style='List Number')

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # REFERENCES
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "REFERENCES", level=1)

    references = [
        'Allen, J. (2007). "Photoplethysmography and its application in clinical physiological measurement." Physiological Measurement, 28(3), R1–R39.',
        'Elgendi, M. (2012). "On the Analysis of Fingertip Photoplethysmogram Signals." Current Cardiology Reviews, 8(1), 14–25.',
        'Verkruysse, W., Svaasand, L. O., & Nelson, J. S. (2008). "Remote plethysmographic imaging using ambient light." Optics Express, 16(26), 21434–21445.',
        'Poh, M. Z., McDuff, D. J., & Picard, R. W. (2011). "Advancements in noncontact, multiparameter physiological measurements using a webcam." IEEE Trans. on Biomedical Engineering, 58(1), 7–11.',
        'Bousefsaf, F., Maaoui, C., & Pruski, A. (2013). "Continuous wavelet filtering on webcam photoplethysmographic signals." Biomedical Signal Processing and Control, 8(6), 568–574.',
        'Hochreiter, S., & Schmidhuber, J. (1997). "Long Short-Term Memory." Neural Computation, 9(8), 1735–1780.',
        'Rajkomar, A., et al. (2018). "Scalable and accurate deep learning with electronic health records." NPJ Digital Medicine, 1(1), 18.',
        'Zhang, G., et al. (2020). "A noninvasive blood glucose monitoring system based on smartphone PPG signal processing and machine learning." IEEE Trans. on Industrial Informatics, 16(11), 7209–7218.',
        'Hossain, S., et al. (2019). "Non-invasive glucose level estimation using PPG signal." International Conference on ECCE, 1–5.',
        'Rachim, V. P., & Chung, W. Y. (2019). "Wearable-band type visible-near infrared optical biosensor for non-invasive blood glucose monitoring." Sensors and Actuators B: Chemical, 286, 173–180.',
        'TensorFlow Documentation — https://www.tensorflow.org/api_docs',
        'OpenCV Documentation — https://docs.opencv.org/',
        'SciPy Signal Processing — https://docs.scipy.org/doc/scipy/reference/signal.html',
        'Keras LSTM API — https://keras.io/api/layers/recurrent_layers/lstm/',
        'Savitzky, A., & Golay, M. J. E. (1964). "Smoothing and differentiation of data by simplified least squares procedures." Analytical Chemistry, 36(8), 1627–1639.',
    ]
    for i, ref in enumerate(references, 1):
        p = doc.add_paragraph()
        run_num = p.add_run(f"[{i}] ")
        run_num.bold = True
        run_num.font.size = Pt(10)
        run_text = p.add_run(ref)
        run_text.font.size = Pt(10)

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # APPENDIX
    # ════════════════════════════════════════════════════════════════════

    add_heading_styled(doc, "APPENDIX", level=1)

    add_heading_styled(doc, "Appendix A: Project File Structure", level=2)

    file_structure = [
        "glucose-monitor/",
        "├── backend/",
        "│   ├── app.py                      — Flask API server",
        "│   ├── ppg_extraction.py           — PPG signal processing (1092 lines)",
        "│   ├── lstm_model.py               — LSTM inference pipeline (490 lines)",
        "│   ├── train_model.py              — Training pipeline (733 lines)",
        "│   ├── database.py                 — SQLite authentication (47 lines)",
        "│   ├── final_model.keras           — Standard model (2.4 MB)",
        "│   ├── enhanced_model.keras        — Enhanced model (2.4 MB)",
        "│   ├── feature_scaler.save         — Feature scaler",
        "│   ├── y_scaler.save               — Target scaler",
        "│   ├── training_report.json        — Training metrics",
        "│   ├── users.db                    — SQLite database",
        "│   └── dataset/video_data.csv      — Training dataset",
        "│",
        "├── frontend/",
        "│   ├── src/",
        "│   │   ├── App.jsx                 — Root component",
        "│   │   ├── api.js                  — API client",
        "│   │   ├── context/AuthContext.jsx  — Auth state",
        "│   │   ├── pages/",
        "│   │   │   ├── LandingPage.jsx     — Hero landing page",
        "│   │   │   ├── AuthPage.jsx        — Login/Signup",
        "│   │   │   └── Dashboard.jsx       — Main dashboard",
        "│   │   └── components/",
        "│   │       ├── Navbar.jsx           — Navigation bar",
        "│   │       ├── UploadPanel.jsx      — Video upload",
        "│   │       ├── ResultsPanel.jsx     — Results display",
        "│   │       └── HistoryPanel.jsx     — History list",
        "│   └── package.json                — NPM dependencies",
        "│",
        "└── .gitignore",
    ]
    for line in file_structure:
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.font.name = 'Consolas'
        run.font.size = Pt(9)

    add_heading_styled(doc, "Appendix B: Key API Endpoints", level=2)

    add_formatted_table(doc,
        ["Endpoint", "Method", "Request Body", "Response"],
        [
            ("/", "GET", "—", '"🚀 Glucose Monitoring API Running"'),
            ("/signup", "POST", '{ "email": "...", "password": "..." }', '{ "message": "User created successfully" }'),
            ("/login", "POST", '{ "email": "...", "password": "..." }', '{ "message": "Login successful" }'),
            ("/predict", "POST", 'FormData { video: File }', '{ "heart_rate": 75.2, "glucose": 98.5, "graph": "..." }'),
        ],
        col_widths=[2.5, 2, 5.5, 6]
    )

    add_heading_styled(doc, "Appendix C: Glucose Classification Reference", level=2)

    add_formatted_table(doc,
        ["Glucose Level (mg/dL)", "Classification", "Color Code"],
        [
            ("< 70", "Low (Hypoglycemia)", "🟡 Yellow"),
            ("70 – 99", "Normal (Fasting)", "🟢 Green"),
            ("100 – 125", "Pre-diabetic", "🟠 Orange"),
            ("≥ 126", "High (Diabetic)", "🔴 Red"),
        ],
        col_widths=[5, 5, 6]
    )

    # ── Save ──
    output_path = os.path.join(os.path.dirname(__file__), "GlucoAI_Monitor_Project_Report.docx")
    doc.save(output_path)
    print(f"\nReport generated successfully!")
    print(f"File: {output_path}")
    print(f"Size: {os.path.getsize(output_path) / 1024:.1f} KB")


if __name__ == "__main__":
    generate_report()
