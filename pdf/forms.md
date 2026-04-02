# PDF Form Filling Guide

This guide provides step-by-step instructions for filling PDF forms using the scripts in the `scripts/` directory.

## Available Scripts Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `check_fillable_fields.py` | Check if PDF has fillable form fields | `python scripts/check_fillable_fields.py <input.pdf>` |
| `extract_form_field_info.py` | Extract fillable field info to JSON | `python scripts/extract_form_field_info.py <input.pdf> <output.json>` |
| `extract_form_structure.py` | Extract text labels, lines, checkboxes | `python scripts/extract_form_structure.py <input.pdf> <output.json>` |
| `convert_pdf_to_images.py` | Convert PDF pages to PNG images | `python scripts/convert_pdf_to_images.py <input.pdf> <output_dir/>` |
| `check_bounding_boxes.py` | Validate bounding box coordinates | `python scripts/check_bounding_boxes.py <fields.json>` |
| `fill_fillable_fields.py` | Fill PDFs with fillable form fields | `python scripts/fill_fillable_fields.py <input.pdf> <fields.json> <output.pdf>` |
| `fill_pdf_form_with_annotations.py` | Fill PDFs without form fields | `python scripts/fill_pdf_form_with_annotations.py <input.pdf> <fields.json> <output.pdf>` |
| `create_validation_image.py` | Create image with bounding box overlay | `python scripts/create_validation_image.py <page> <fields.json> <input.png> <output.png>` |

---

## Quick Decision Flow

```
                    ┌─────────────────────────────┐
                    │ Need to fill a PDF form?    │
                    └─────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │ python scripts/check_fillable_fields.py <input.pdf>
              └─────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        "has fillable fields"      "does not have fillable fields"
                    │                       │
                    ▼                       ▼
           ┌───────────────┐       ┌───────────────────┐
           │ Fillable Path │       │ Non-Fillable Path │
           └───────────────┘       └───────────────────┘
```

---

## Path A: Fillable Form Fields

Use this path when the PDF has fillable form fields (detected by `check_fillable_fields.py`).

### Step A.1: Extract Field Information

```bash
python scripts/extract_form_field_info.py <input.pdf> field_info.json
```

Output JSON format:
```json
[
  {
    "field_id": "last_name",
    "page": 1,
    "rect": [50, 700, 200, 720],
    "type": "text"
  },
  {
    "field_id": "checkbox_agree",
    "page": 1,
    "rect": [50, 650, 65, 665],
    "type": "checkbox",
    "checked_value": "/Yes",
    "unchecked_value": "/Off"
  },
  {
    "field_id": "gender",
    "page": 1,
    "type": "radio_group",
    "radio_options": [
      {"value": "/Male", "rect": [50, 600, 65, 615]},
      {"value": "/Female", "rect": [100, 600, 115, 615]}
    ]
  },
  {
    "field_id": "country",
    "page": 1,
    "type": "choice",
    "choice_options": [
      {"value": "US", "text": "United States"},
      {"value": "CN", "text": "China"}
    ]
  }
]
```

### Step A.2: Convert to Images for Analysis

```bash
python scripts/convert_pdf_to_images.py <input.pdf> images/
```

This creates `images/page_1.png`, `images/page_2.png`, etc.

### Step A.3: Create Field Values JSON

Create `field_values.json` with the values to fill:

```json
[
  {
    "field_id": "last_name",
    "description": "User's last name",
    "page": 1,
    "value": "Smith"
  },
  {
    "field_id": "checkbox_agree",
    "description": "Agreement checkbox",
    "page": 1,
    "value": "/Yes"
  },
  {
    "field_id": "gender",
    "description": "Gender selection",
    "page": 1,
    "value": "/Male"
  },
  {
    "field_id": "country",
    "description": "Country selection",
    "page": 1,
    "value": "CN"
  }
]
```

**Important**: 
- For checkboxes: use `checked_value` to check, `/Off` to uncheck
- For radio groups: use one of the `radio_options[].value`
- For choice fields: use one of the `choice_options[].value`

### Step A.4: Fill the Form

```bash
python scripts/fill_fillable_fields.py <input.pdf> field_values.json <output.pdf>
```

The script validates field IDs and values before filling. If errors occur, fix them and retry.

---

## Path B: Non-Fillable Forms

Use this path when the PDF does NOT have fillable form fields (scanned PDFs, flat forms, etc.).

### Step B.1: Extract Form Structure

```bash
python scripts/extract_form_structure.py <input.pdf> form_structure.json
```

Output JSON format:
```json
{
  "pages": [
    {"page_number": 1, "width": 612, "height": 792}
  ],
  "labels": [
    {"page": 1, "text": "Last Name", "x0": 50, "top": 100, "x1": 120, "bottom": 115}
  ],
  "lines": [
    {"page": 1, "y": 150, "x0": 50, "x1": 550}
  ],
  "checkboxes": [
    {"page": 1, "x0": 50, "top": 200, "x1": 62, "bottom": 212, "center_x": 56, "center_y": 206}
  ],
  "row_boundaries": [
    {"page": 1, "row_top": 100, "row_bottom": 150, "row_height": 50}
  ]
}
```

**Check the results**: 
- If `labels` has meaningful text → use **Structure-Based Approach**
- If `labels` is empty or shows "(cid:X)" patterns → use **Visual Estimation Approach**

### Step B.2: Convert to Images

```bash
python scripts/convert_pdf_to_images.py <input.pdf> images/
```

---

### Approach B-A: Structure-Based Coordinates (Preferred)

Use when `extract_form_structure.py` found text labels.

#### B-A.1: Analyze the Structure

1. **Label groups**: Adjacent text elements form a single label (e.g., "Last" + "Name")
2. **Row structure**: Labels with similar `top` values are in the same row
3. **Field columns**: Entry areas start after label ends (x0 = label.x1 + gap)
4. **Checkboxes**: Use coordinates directly from `checkboxes` array

**Coordinate system**: PDF coordinates where y=0 is at TOP of page, y increases downward.

#### B-A.2: Create fields.json

```json
{
  "pages": [
    {"page_number": 1, "pdf_width": 612, "pdf_height": 792}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Last name entry field",
      "field_label": "Last Name",
      "label_bounding_box": [50, 100, 120, 115],
      "entry_bounding_box": [125, 100, 300, 118],
      "entry_text": {"text": "Smith", "font_size": 10}
    },
    {
      "page_number": 1,
      "description": "Agree checkbox",
      "field_label": "Agree",
      "label_bounding_box": [70, 200, 100, 212],
      "entry_bounding_box": [50, 200, 62, 212],
      "entry_text": {"text": "X", "font_size": 10}
    }
  ]
}
```

**Important**: Use `pdf_width`/`pdf_height` to indicate PDF coordinates.

---

### Approach B-B: Visual Estimation (Fallback)

Use when the PDF is scanned/image-based and structure extraction found no usable labels.

#### B-B.1: Get Image Dimensions

Check the generated image dimensions from `convert_pdf_to_images.py` output.

#### B-B.2: Estimate Field Coordinates

Examine each page image to identify:
- Form field labels and their positions
- Entry areas (lines, boxes, blank spaces)
- Checkboxes and their locations

#### B-B.3: Create fields.json with Image Coordinates

```json
{
  "pages": [
    {"page_number": 1, "image_width": 1700, "image_height": 2200}
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "Last name entry field",
      "field_label": "Last Name",
      "label_bounding_box": [140, 280, 340, 320],
      "entry_bounding_box": [350, 280, 850, 330],
      "entry_text": {"text": "Smith", "font_size": 14}
    }
  ]
}
```

**Important**: Use `image_width`/`image_height` to indicate image coordinates.

---

### Step B.3: Validate Bounding Boxes

**Always validate before filling:**

```bash
python scripts/check_bounding_boxes.py fields.json
```

This checks for:
- Intersecting bounding boxes (would cause overlapping text)
- Entry boxes too small for the font size

### Step B.4: Visual Validation (Optional)

Create a validation image to visually check bounding boxes:

```bash
python scripts/create_validation_image.py 1 fields.json images/page_1.png validation.png
```

- Red boxes: entry bounding boxes
- Blue boxes: label bounding boxes

### Step B.5: Fill the Form

```bash
python scripts/fill_pdf_form_with_annotations.py <input.pdf> fields.json <output.pdf>
```

The script auto-detects coordinate system (PDF or image) and handles conversion.

### Step B.6: Verify Output

```bash
python scripts/convert_pdf_to_images.py <output.pdf> verify_images/
```

Check the images to verify text placement is correct.

---

## Chinese Text Support (中文支持)

**重要**: 填写中文表单时，需要在 `entry_text` 中指定中文字体：

```json
{
  "page_number": 1,
  "description": "姓名字段",
  "field_label": "姓名",
  "label_bounding_box": [50, 100, 100, 115],
  "entry_bounding_box": [105, 100, 250, 118],
  "entry_text": {
    "text": "张三",
    "font_name": "simsun",
    "font_size": 12
  }
}
```

**Available Chinese fonts** (Windows):
- `simsun` - 宋体
- `simhei` - 黑体
- `microsoftyahei` - 微软雅黑
- `kaiti` - 楷体
- `fangsong` - 仿宋
- `dengxian` - 等线

**Font color** (optional):
```json
"entry_text": {
  "text": "张三",
  "font_name": "simsun",
  "font_size": 12,
  "font_color": "000000"
}
```

---

## Hybrid Approach: Structure + Visual

Use when structure extraction works for most fields but misses some elements.

1. Use **Approach B-A** for detected fields
2. Convert PDF to images for visual analysis of missing fields
3. Convert image coordinates to PDF coordinates:
   - `pdf_x = image_x * (pdf_width / image_width)`
   - `pdf_y = image_y * (pdf_height / image_height)`
4. Use single coordinate system in fields.json (`pdf_width`/`pdf_height`)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Text appears as black boxes | Register Chinese font with `font_name` |
| Text is mispositioned | Check coordinate system matches (`pdf_width` vs `image_width`) |
| Bounding boxes intersect | Run `check_bounding_boxes.py` and fix errors |
| Text is cut off | Increase entry box height or decrease font size |
| Checkbox not checked | Verify using correct `checked_value` from field_info.json |
| Radio button not selected | Use exact value from `radio_options[].value` |

---

## Complete Workflow Example

```bash
# Step 1: Check if fillable
python scripts/check_fillable_fields.py form.pdf

# If fillable:
python scripts/extract_form_field_info.py form.pdf field_info.json
python scripts/convert_pdf_to_images.py form.pdf images/
# ... create field_values.json ...
python scripts/fill_fillable_fields.py form.pdf field_values.json output.pdf

# If not fillable:
python scripts/extract_form_structure.py form.pdf form_structure.json
python scripts/convert_pdf_to_images.py form.pdf images/
# ... create fields.json ...
python scripts/check_bounding_boxes.py fields.json
python scripts/create_validation_image.py 1 fields.json images/page_1.png validation.png
python scripts/fill_pdf_form_with_annotations.py form.pdf fields.json output.pdf
python scripts/convert_pdf_to_images.py output.pdf verify/
```
