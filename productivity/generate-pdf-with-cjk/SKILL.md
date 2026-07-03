---
name: generate-pdf-with-cjk
description: "Generate PDFs with Chinese (CJK) text on UGREEN NAS. Three approaches tested and ranked: Typst (best), WeasyPrint (reliable fallback), fpdf2 (lightweight, no emoji). Includes emoji rendering guide."
version: 2.2.0
metadata:
  hermes:
    tags: [PDF, CJK, Chinese, weasyprint, typst, fpdf2, Document Generation, emoji]
---

# Generate PDF with CJK (Chinese) Text — 2026-06-29 全面评测

## 方案对比（按推荐优先级）

| 方案 | CJK | Emoji | 表格 | 代码 | PDF大小 | 安装 | 评级 |
|------|------|-------|------|------|---------|------|----------|
| **Typst** | 原生 | 原生 | 支持 | 支持 | ~97KB | 需手动安装 | 首选 |
| WeasyPrint | CSS @font-face | 需 span.e | 支持 | 支持 | 288~553KB | 需 pip install | 可靠 |
| fpdf2 | add_font(.ttc) | 不支持 | 基础 | 不支持 | ~31KB | 需 pip install | 轻量 |

**结论：Typst 最适合学术周报等复杂文档，fpdf2 适合简单表格报告。**

---

## 方案一：Typst（推荐）

### 简介
Typst 是现代排版系统，CJK 和 Emoji 均开箱即用。

### ⚠️ 依赖管理
所有依赖已 bake 进标准镜像 (hermes-agent:v0.17.0+)。容器重建后不丢失，无需手动安装。

### CJK 字体
Typst 自动检测 `Noto Sans CJK SC` 等系统字体。在文档顶部声明即可：

```typst
#set text(font: ("Noto Sans CJK SC", "Noto Color Emoji"), size: 11pt)
```

### 完整模板

```typst
// 页面设置
#set page(paper: "a4", margin: (top: 2cm, bottom: 2cm, left: 2.5cm, right: 2.5cm))
// 字体设置 CJK + Emoji 同时加载
#set text(font: ("Noto Sans CJK SC", "Noto Color Emoji"), size: 11pt)

// 标题
#text(size: 20pt, weight: "bold")[ 烟雾检测周报 Week 27 ]
#line(length: 100%)
#v(0.5cm)

// 元数据
#text(size: 10pt, fill: gray)[Hermes Agent 2026-06-29]
#v(0.5cm)

= 一级标题
== 二级标题

**粗体文字** 和 _斜体文字_

- 列表项
- 代码: #raw("import numpy as np")
- Emoji

// 表格
#table(
  columns: (1fr, 1.5fr, 2fr),
  inset: 8pt,
  stroke: 0.5pt,
  [*论文*], [*第一作者*], [*所属机构*],
  [VTrUNet], [Liang Zhao], [UniSA],
)
```

### 生成命令

```bash
typst compile input.typ output.pdf
# 监视文件变化自动编译
typst watch input.typ
```

### 已知问题

- **Typst 不支持用 `.ttc` 文件直接指定字体路径**。确保字体已安装到系统目录。
- **字体自动发现**：如果 `Noto Sans CJK SC` 未找到（容器默认只有文泉驿正黑），通过 `fc-list :lang=zh` 查看可用字体名。字体声明示例：`#set text(font: ("WenQuanYi Zen Hei", "Unifont"), size: 10pt, lang: "zh")`
- **`#sym.*` 命令不可用**：Typst 的 `#sym` 模块只含 `sym.arrow`, `sym.bullet` 等少量符号，**没有** `sym.ge`（≥）、`sym.checkmark`（✓）、`sym.arrow` 也不推荐。Markdown→Typst 转换时必须将 `#sym.ge` → `≥`（直接 Unicode）、`#sym.arrow` → `→`、`#sym.checkmark` → `✓`、`#sym.bullet` → `•`。最佳实践：**Typography 中标点符号直接用 Unicode 字符**，避免依赖 `#sym` 模块。

---

## 方案二：WeasyPrint

### 简介
HTML 转 PDF。可靠但 PDF 体积较大。

### CJK 字体
需要 CSS `@font-face` 声明。`/usr/share/fonts/opentype/noto/` 下有 .ttc 文件，WeasyPrint 原生支持 TTC。

```css
@font-face {
    font-family: 'Noto CJK';
    src: url('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc');
}
@font-face {
    font-family: 'Noto CJK Bold';
    src: url('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc');
}
body { font-family: 'Noto CJK', sans-serif; }
h1 { font-family: 'Noto CJK Bold', sans-serif; }
```

### 完整模板

```python
#!/usr/bin/env python3
import os
from weasyprint import HTML as WeasyHTML

HTML_CONTENT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 20mm; }
body { font-family: 'Noto CJK', sans-serif; font-size: 10pt; line-height: 1.6; }
.e { font-family: 'Noto Emoji', 'Noto CJK', sans-serif; }
</style>
</head>
<body>
<p>Emoji 必须用 span.e 包裹</p>
<p>状态: <span class="e">emoji</span> 已完成</p>
</body>
</html>"""

output_path = '/home/vive/Work/Hermes/output.pdf'
WeasyHTML(string=HTML_CONTENT).write_pdf(output_path)
print(f'PDF saved {output_path} ({os.path.getsize(output_path)} bytes)')
```

### 关键坑点
1. **变量名冲突**：别用 `HTML` 做变量名。用 `from weasyprint import HTML as WeasyHTML`。
2. **Emoji 必须用 `<span class="e">` 包裹**，否则 CJK 字体会抢 emoji glyph 显示为方块。
3. **CSS font-family 名称**：用 `'Noto CJK'` 而非文件名。CSS 中声明的 font-family 名称可以任意，只要和 @font-face 中的一致。
4. **PDF 体积较大**：带 CJK+emoji 的典型周报约 288~553KB。

---

## 方案三：fpdf2（轻量场景）

### 适用场景
- 简单报告、证书、纯 CJK 文本
- 不需要 emoji 的文档

### 示例

```python
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.add_font('NotoSans', '', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
pdf.add_font('NotoSans', 'B', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')
pdf.set_font('NotoSans', '', 18)
pdf.cell(text='标题', new_x="LMARGIN", new_y="NEXT")
pdf.set_font('NotoSans', '', 11)
pdf.multi_cell(w=0, text='正文内容')
pdf.output('/path/to/output.pdf')
```

### 已知限制
- **不支持 emoji** emoji 会显示为方块
- **不支持 Markdown/HTML 标记** 需要手动调用 set_font 切换样式
- 表格功能基本可用但外观较朴素

---

## Emoji 渲染对比

| 方案 | Emoji 支持 | 额外配置 | 效果 |
|------|-----------|----------|------|
| Typst | 原生 | 无 | 完美 |
| WeasyPrint | 有条件 | 需 span.e + CSS | 良好 |
| fpdf2 | 不支持 | 无 | 显示为方块 |

### WeasyPrint Emoji 方案详解

WeasyPrint 能正确渲染 emoji，但需要正确的字体回退策略：

```css
@font-face {
    font-family: 'Noto Emoji';
    src: url('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf');
}
.e { font-family: 'Noto Emoji', 'Noto CJK', sans-serif; }
```

如果系统没有 Noto Color Emoji 字体，可以使用 Segoe UI Emoji 或 Twemoji Mozilla 等。

---

## 安装检查（每次使用前必做）

### 第一步：快速状态检查
```bash
which typst && typst --version    # Typst
python3 -c "from weasyprint import HTML" 2>&1   # WeasyPrint
python3 -c "from fpdf import FPDF" 2>&1         # fpdf2
fc-list :lang=zh | head -3                       # CJK 字体
```

### 第二步：依赖状态
**依赖已 bake 进标准镜像 (hermes-agent:v0.17.0+)，容器重建不丢失。**
如果缺失 → 报告 `dependency_missing=true` → 建议重建 baked image。
**不要 runtime apt-get/curl 修补。**

```bash
# Typst — baked into standard image (hermes-agent:v0.17.0+)
# /usr/local/bin/typst, no manual install needed
which typst && typst --version

# WeasyPrint + fpdf2 — baked into standard image
python3 -c "from weasyprint import HTML; print('OK')"
python3 -c "from fpdf import FPDF; print('OK')"

# CJK fonts — baked into standard image
fc-list :lang=zh | head -1
```

### 第三步：字体兼容
如果 `Noto Sans CJK SC` 不存在，Typst 可使用文泉驿正黑：
```typst
#set text(font: ("WenQuanYi Zen Hei", "Noto Color Emoji"), size: 10pt, lang: "zh")
```
查找可用 CJK 字体：`fc-list :lang=zh`

---

## Hermes 产出文件规则

所有 PDF 生成文件放在：
```
/home/vive/Work/Hermes/YYYY-MM-DD-描述性名称/
```

目录不存在时主动创建：
```python
import os
os.makedirs('/home/vive/Work/Hermes/YYYY-MM-DD-description', exist_ok=True)
```