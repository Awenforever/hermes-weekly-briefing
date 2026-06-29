#!/usr/bin/env python3
"""Regenerate briefing PDF using weasyprint (HTML → PDF) with proper CJK rendering."""

import os

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@page {
    size: A4;
    margin: 20mm;
    @bottom-center {
        content: "Page " counter(page) " / " counter(pages);
        font-size: 8pt;
        color: #999;
    }
}
body {
    font-family: 'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'Microsoft YaHei', sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #333;
}
.cover { page-break-after: always; text-align: center; padding-top: 80px; }
.cover h1 { font-size: 26pt; color: #19375f; margin-bottom: 8px; }
.cover h2 { font-size: 16pt; color: #3c3c3c; margin-bottom: 20px; }
.cover .date { font-size: 12pt; color: #787878; }
.cover .divider { width: 120mm; margin: 20px auto; border-top: 2px solid #19375f; }
.cover .tags { font-size: 10pt; color: #505050; margin-top: 20px; }
h3.section { font-size: 14pt; color: #19375f; margin-top: 16px; page-break-inside: avoid; }
.paper { margin-bottom: 20px; page-break-inside: avoid; }
.paper .num { display: inline-block; background: #19375f; color: #fff; padding: 1px 6px;
             font-size: 10pt; margin-right: 6px; vertical-align: middle; }
.paper h4 { display: inline; font-size: 13pt; color: #19375f; margin: 0; }
.paper .en-title { font-size: 9pt; color: #505050; font-style: italic; margin: 4px 0;
                   padding-left: 10px; }
.paper .field { margin: 4px 0 4px 10px; }
.paper .field-label { font-weight: bold; color: #323232; }
.paper .abstract { margin: 6px 0 6px 10px; }
.paper .abstract-title { font-weight: bold; color: #19375f; font-size: 10pt; }
.paper .key-points { margin: 6px 0 6px 10px; }
.paper .key-points-title { font-weight: bold; color: #19375f; font-size: 10pt; }
.paper .key-points li { font-size: 10pt; margin: 2px 0; }
.paper .insight { margin: 8px 0 8px 10px; padding: 8px; background: #f0f5fa;
                  border: 1px solid #c8d2e1; border-radius: 3px; font-size: 10pt; }
.paper .author-team { margin: 8px 0 8px 10px; padding: 8px; background: #faf5f0;
                      border: 1px solid #ddd0c0; border-radius: 3px; font-size: 10pt; }
.paper .author-team-title { font-weight: bold; color: #8b4513; font-size: 10pt; }
.author-table { width: 100%; border-collapse: collapse; margin: 4px 0; }
.author-table td { padding: 2px 6px; font-size: 9pt; text-align: left; border: none; }
.author-table .alabel { font-weight: bold; color: #555; width: 90px; vertical-align: top; }
.table-page { page-break-before: always; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; }
th { background: #19375f; color: #fff; padding: 4px; font-size: 8pt; text-align: center; border: 1px solid #19375f; }
td { padding: 4px; font-size: 8pt; text-align: center; border: 1px solid #ccc; }
tr:nth-child(even) { background: #f5f8fc; }
.trend-page { page-break-before: always; }
.trend-item { margin: 8px 0; page-break-inside: avoid; }
.trend-item h5 { font-size: 10pt; color: #19375f; margin: 0 0 4px 0; }
.trend-item p { font-size: 9pt; color: #3c3c3c; margin: 0; }
.highlight { background: #f0f5fa; border: 1px solid #c8d2e1; padding: 8px;
             border-radius: 3px; margin: 10px 0; font-size: 10pt; }
</style>
</head>
<body>

<div class="cover">
<h1>学术研究周报</h1>
<h2>遥感多光谱野火烟雾检测前沿</h2>
<div class="date">2026年第27周 (6.29 - 7.5)</div>
<div class="divider"></div>
<div class="tags">
<div>方向：多光谱卫星影像烟雾检测 / 分割 / 反演</div>
<div>数据集：USTC_SmokeRS, Landsat, Sentinel-2, MODIS</div>
<div>技术栈：Transformer, CNN, UNet, 轻量化, 物理模型</div>
</div>
</div>

<!-- ====================================================================== -->
<!-- Paper 1 -->
<!-- ====================================================================== -->
<div class="paper">
<span class="num">[1]</span><h4>基于Transformer增强UNet的多光谱Landsat影像复杂背景烟雾分割</h4>
<div class="en-title">A transformer boosted UNet for smoke segmentation in complex backgrounds in multispectral LandSat imagery</div>
<div class="field"><span class="field-label">第一/通信作者</span> Jixue Liu* (通讯作者), 第一作者 Liang Zhao</div>
<div class="field"><span class="field-label">机构</span> UniSA STEM, University of South Australia (南澳大学)</div>
<div class="field"><span class="field-label">发表于</span> Remote Sensing Applications: Society and Environment, 2024</div>
<div class="field"><span class="field-label">DOI</span> https://doi.org/10.1016/j.rsase.2024.101152<br>
  arXiv: https://arxiv.org/abs/2406.13105</div>
<div class="abstract">
<div class="abstract-title">摘要与核心贡献</div>
本文提出VTrUNet模型，在UNet架构中融合Transformer自注意力机制，专门针对多光谱Landsat影像中的复杂背景烟雾分割。模型包含两个核心创新：1) 虚拟通道构建模块(Virtual Band Construction)，将输入的6波段(RGB+NIR+SWIR1+SWIR2)扩展为更高维度的特征空间，使特定通道与光谱模式对齐；2) 在每个UNet层级嵌入Vision Transformer块，利用自注意力机制捕捉区域间长程上下文关联，对薄烟的语义推断尤为有效。实验表明，VTrUNet在F1分数上较Smoke-UNet、GFUNet、MA-UNet等最新方法提升超过4%，是首个能同时在晴朗、雾霾、云层遮挡和云阴影等复杂场景下稳定检测烟雾的模型。
</div>
<div class="key-points">
<div class="key-points-title">关键数据与发现</div>
<ul>
<li>输入：Landsat 6波段 (B3蓝光, B4绿光, B5红光, B6近红外, B7短波红外1, B8短波红外2)</li>
<li>虚拟通道构建将光谱特征映射到更高分辨率的表示空间</li>
<li>Transformer注意力机制专注于对比区域均值与最大值差异，增强薄烟判别</li>
<li>F1分数超过其他方法4%以上，尤其在薄烟检测中优势明显</li>
<li>提出新的评估指标：针对重叠场景的模型评估方案</li>
</ul>
</div>
<div class="author-team">
<div class="author-team-title">🧑‍🏫 作者团队背景</div>
<table class="author-table">
<tr><td class="alabel">团队简介</td><td>南澳大学(UniSA) STEM学院遥感与数据科学研究团队，长期从事卫星影像中的火灾烟雾检测、土地覆盖分类等方向。团队近年来连续在多光谱烟雾检测方向发表系列成果（2022-2024）。</td></tr>
<tr><td class="alabel">核心作者</td><td><b>Jiuyong Li</b> (h-index 47, 9,267+ citations)：教授，数据挖掘与机器学习领域资深专家；<b>Jixue Liu</b> (h-index 27, 2,757+ citations)：副教授，通讯作者，主导本文的算法设计与实验；<b>Stefan Peters</b> (h-index 14)：遥感数据科学家，负责数据处理与验证。</td></tr>
<tr><td class="alabel">相关积累</td><td>团队前期工作：Liang Zhao等2022年发表关于Landsat影像轻量CNN火灾烟雾检测（Remote Sensing）；2024年发表基于类特定光谱模式的深度学习方法（RSASE）；本文是前述工作的延续与深化。</td></tr>
<tr><td class="alabel">合作网络</td><td>与澳大利亚SmartSat CRC（合作研究中心）有项目合作，获其研究资助支持。</td></tr>
</table>
</div>
<div class="insight"><b>对博士论文的启示:</b> 虚拟通道构建的思想与InAmp模块高度相似（后者使用了USTC_SmokeRS数据集），说明光谱特征工程在烟雾检测领域具有通用价值。建议在模型设计中引入类似机制。</div>
</div>

<!-- ====================================================================== -->
<!-- Paper 2 -->
<!-- ====================================================================== -->
<div class="paper">
<span class="num">[2]</span><h4>卫星影像多注意力交错网络用于早期野火烟雾检测</h4>
<div class="en-title">Satellite Image-Based Surveillance and Early Wildfire Smoke Detection Using a Multiattention Interlaced Network</div>
<div class="field"><span class="field-label">第一/通信作者</span> Shubhangi Chaturvedi* (通讯作者), Poornima Singh Thakur (第一作者)</div>
<div class="field"><span class="field-label">机构</span> Bennett University (本内特大学), India; IIITDM Jabalpur; Curtin University, Australia</div>
<div class="field"><span class="field-label">发表于</span> IEEE Transactions on Industrial Informatics, 2025</div>
<div class="field"><span class="field-label">DOI</span> https://doi.org/10.1109/tii.2025.3528549</div>
<div class="abstract">
<div class="abstract-title">摘要与核心贡献</div>
本文提出一种将Vision Transformer与CNN交错融合的多注意力网络，用于卫星影像中的早期野火烟雾检测。模型在云、雾、飓风、风暴、降雪等多种恶劣大气条件下进行测试，验证了泛化能力。核心创新在于交错架构设计——ViT与CNN块交替堆叠，而非简单的串联或拼接。模型仅含0.7M参数、0.2 GFLOPs计算量，适合部署在基于物联网的森林和工业监控系统上。在IIITDMJ_Smoke数据集上误报降低30%，在USTC_SmokeRS上误报降低6%。
</div>
<div class="key-points">
<div class="key-points-title">关键数据与发现</div>
<ul>
<li>模型参数量：0.7M (仅约为ResNet50的1/10)</li>
<li>计算量：0.2 GFLOPs，可在IoT边缘设备实时运行</li>
<li>可检测图像面积仅2%的微小烟雾区域（早期预警关键指标）</li>
<li>误报率降低：IIITDMJ -30%, USTC_SmokeRS -6%</li>
<li>额外测试：工业烟囱烟雾、户外视频烟雾场景均有良好表现</li>
</ul>
</div>
<div class="author-team">
<div class="author-team-title">🧑‍🏫 作者团队背景</div>
<table class="author-table">
<tr><td class="alabel">团队简介</td><td>印度-Bennett大学、IIITDM Jabalpur与澳大利亚Curtin大学国际合作团队。Bennett大学在计算机视觉与模式识别方向有活跃研究组；IIITDM Jabalpur的Pritee Khanna教授团队专注于烟火检测多年。</td></tr>
<tr><td class="alabel">核心作者</td><td><b>Shubhangi Chaturvedi</b>* (通讯作者, Bennett University)：在烟雾检测领域有系列论文，涵盖CNN/Transformer/ViT等多种架构，发表过烟雾检测综述论文；<b>Pritee Khanna</b> (IIITDM Jabalpur)：教授，模式识别专家；<b>Yongze Song</b> (Curtin University)：遥感与空间统计方向。</td></tr>
<tr><td class="alabel">相关积累</td><td>团队在烟雾检测方向有较多积累：CNN-based smoke detection, Transformer-based wildfire monitoring 等均有成果。本文的"交错"架构是其系列工作中对ViT+CNN融合方式的最新探索。</td></tr>
<tr><td class="alabel">特色数据</td><td>使用了自建的 IIITDMJ_Smoke 数据集（含多种恶劣大气条件），并公开在 USTC_SmokeRS 上进行评测。</td></tr>
</table>
</div>
<div class="insight"><b>对博士论文的启示:</b> 参数量如此小的模型能达到SOTA水平，说明当前烟雾检测任务中模型过大可能存在冗余。如果你要做博士论文的模型设计，轻量化+高精度是一个很好的卖点。</div>
</div>

<!-- ====================================================================== -->
<!-- Paper 3 -->
<!-- ====================================================================== -->
<div class="paper">
<span class="num">[3]</span><h4>多尺度CNN-Transformer混合网络用于卫星影像烟雾检测</h4>
<div class="en-title">Multi-Scale Hybrid CNN-Transformer for Smoke Detection in Satellite Images</div>
<div class="field"><span class="field-label">第一/通信作者</span> Tony Zhang* (通讯作者/第一作者), Robert P. Dick</div>
<div class="field"><span class="field-label">机构</span> Department of Electrical and Computer Engineering, University of Michigan–Ann Arbor (密歇根大学安娜堡分校)</div>
<div class="field"><span class="field-label">发表于</span> ICCV Workshops, 2025</div>
<div class="field"><span class="field-label">DOI</span> https://doi.org/10.1109/iccvw69036.2025.00305</div>
<div class="abstract">
<div class="abstract-title">摘要与核心贡献</div>
本文针对卫星影像烟雾检测中烟雾尺度、形状、纹理多变的挑战，提出了CNN与Transformer的层级混合架构。核心设计：在每一层CNN之后级联Transformer层提取多尺度特征，并在顶层追加额外的Transformer层以捕捉跨感受野的全局关系。该设计充分利用了CNN在局部特征提取上的优势和Transformer在全局长程建模上的能力。在USTC_SmokeRS数据集上进行评估，超越了之前所有方法。
</div>
<div class="key-points">
<div class="key-points-title">关键数据与发现</div>
<ul>
<li>层级混合策略：每个CNN层后接Transformer层，而非端到端的串联</li>
<li>顶层额外Transformer层：捕捉不同感受野之间的跨尺度关系</li>
<li>使用USTC_SmokeRS数据集（6类：smoke, seaside, land, haze, dust, cloud）</li>
<li>解决了传统CNN因卷积局部性导致的全局上下文建模不足问题</li>
</ul>
</div>
<div class="author-team">
<div class="author-team-title">🧑‍🏫 作者团队背景</div>
<table class="author-table">
<tr><td class="alabel">团队简介</td><td>University of Michigan–Ann Arbor (密歇根大学安娜堡分校) 电子工程与计算机系。该团队长期将计算机视觉技术应用于遥感与环境监测。</td></tr>
<tr><td class="alabel">核心作者</td><td><b>Tony Zhang</b> (h-index 3, 22+ citations)：博士生/研究员，研究方向为遥感图像分析、烟雾/火灾检测、大气污染物估算。已连续发表多篇遥感/环境CV论文（ICIP 2019、2023、2024, ICCV 2025）。<b>Robert P. Dick</b> (h-index 43, 8,800+ citations)：教授，嵌入式系统与计算机视觉专家。</td></tr>
<tr><td class="alabel">相关积累</td><td>Tony Zhang在遥感烟火检测方向有完整研究链条：2019年ICIP发表基于图像分析的大气污染物估算；2023年ICIP发表遥感图像空间-频率网络；2024年ICIP发表面向火灾分割的上下文多尺度网络；2025年本文是此方向的集大成之作。</td></tr>
<tr><td class="alabel">合作网络</td><td>密歇根大学ECE系，与多个COTS/硬件安全方向也有交叉合作，显示该组的技术广度。</td></tr>
</table>
</div>
<div class="insight"><b>对博士论文的启示:</b> 与Paper 2的交错架构形成对比：本文是"层级追加"而非"交错"。两种混合方式孰优孰劣尚无定论，这可以作为一个实验变量来探索。</div>
</div>

<!-- ====================================================================== -->
<!-- Paper 4 -->
<!-- ====================================================================== -->
<div class="paper">
<span class="num">[4]</span><h4>Land8Fire：人工标注多光谱野火分割数据集与全面基准测试</h4>
<div class="en-title">Land8Fire: A Complete Study on Wildfire Segmentation Through Comprehensive Review, Human-Annotated Multispectral Dataset, and Extensive Benchmarking</div>
<div class="field"><span class="field-label">作者</span> Tran Anh Tuan, Minh Tran, Enric Marti, et al.</div>
<div class="field"><span class="field-label">机构</span> University of Arkansas (阿肯色大学) 等多机构</div>
<div class="field"><span class="field-label">发表于</span> Remote Sensing, 2025, 17(16), 2776</div>
<div class="field"><span class="field-label">DOI</span> https://doi.org/10.3390/rs17162776</div>
<div class="abstract">
<div class="abstract-title">摘要与核心贡献</div>
本文构建了Land8Fire数据集——包含20,000+人工标注的Landsat 8多光谱图像块，每个图像块均配有高质量的火点分割掩膜。基于ActiveFire数据集改进，提供了标准化的数据划分和基准测试协议。对UNet、DeepLabV3+、SegFormer、Mask2Former等主流分割模型进行系统对比。关键发现：(1) SWIR1 (B6) + SWIR2 (B7) + NIR (B5) 波段组合最优，F1=96.99%, IoU=94.15%；(2) Focal Loss在聚集型火灾场景下反而不如CE Loss，颠覆了"小目标必用Focal Loss"的惯例；(3) 增加波段数不一定提升性能，精选波段更为重要。
</div>
<div class="key-points">
<div class="key-points-title">关键数据与发现</div>
<ul>
<li>数据集规模：20,000+ Landsat 8图像块，全人工标注</li>
<li>最佳波段组合：B5+NIR + B6+SWIR1 + B7+SWIR2 (F1=96.99%)</li>
<li>次优组合：B4+Red + B5+NIR + B6+SWIR1 + B7+SWIR2 (F1=96.39%)</li>
<li>Focal Loss在聚集火灾下Recall反而降低，CE Loss更稳健</li>
<li>SWIR波段对穿透烟雾和云层识别火点至关重要（物理机制）</li>
</ul>
</div>
<div class="author-team">
<div class="author-team-title">🧑‍🏫 作者团队背景</div>
<table class="author-table">
<tr><td class="alabel">团队简介</td><td>以University of Arkansas（阿肯色大学）为主的多机构合作团队。阿肯色大学在地理空间科学与遥感领域有较强实力，特别是在野火监测方向。</td></tr>
<tr><td class="alabel">核心作者</td><td><b>Tran Anh Tuan</b> (第一作者)：博士生，研究方向为多光谱遥感与深度学习野火分割；<b>Enric Marti</b>：资深研究者，在计算机视觉与遥感图像分析方向有长期积累。团队成员还包括越南及欧洲合作者。</td></tr>
<tr><td class="alabel">相关积累</td><td>本团队在野火分割领域有系统性的综述和基准测试工作。本文中的详尽文献综述（涵盖从传统方法到SOTA DL模型）是其他论文中少有的亮点。团队的研究强调数据质量和标准化基准的重要性。</td></tr>
<tr><td class="alabel">特色贡献</td><td>Land8Fire是目前Landsat 8上规模最大的人工标注野火分割数据集，对推动该领域的标准化评估有重要意义。</td></tr>
</table>
</div>
<div class="insight"><b>对博士论文的启示:</b> 这篇论文为你的波段选择实验提供了直接参考。建议在模型中测试 B5+B6+B7 组合，并考虑是否加入B4(红光)。Focal Loss的局限性发现也很有价值。</div>
</div>

<!-- ====================================================================== -->
<!-- Paper 5 -->
<!-- ====================================================================== -->
<div class="paper">
<span class="num">[5]</span><h4>基于细粒度背景识别的改进马氏距离烟雾检测方法</h4>
<div class="en-title">An Improved Mahalanobis Distance Method for Smoke Detection Based on Fine-Grained Background Identification</div>
<div class="field"><span class="field-label">作者</span> Yehan Sun, Lijun Jiang, Jun Pan</div>
<div class="field"><span class="field-label">机构</span> 吉林省科技信息研究所 / 吉林大学等相关机构</div>
<div class="field"><span class="field-label">发表于</span> IEEE Trans. on Geoscience and Remote Sensing, 2026 (Early Access)</div>
<div class="field"><span class="field-label">DOI</span> https://doi.org/10.1109/tgrs.2026.3668811</div>
<div class="abstract">
<div class="abstract-title">摘要与核心贡献</div>
本文提出改进的马氏距离(Mahalanobis Distance)方法，通过细粒度背景识别策略实现烟雾检测。核心思路：将传统物理统计模型与背景细粒度分类相结合，在不同地表背景（植被、水体、裸地、城市）上分别计算最优马氏距离阈值，而非全局统一阈值。该方法实现了跨卫星平台(MODIS/Sentinel/Landsat)的一致检测性能。不同于纯深度学习的黑盒方法，该方法具有可解释性，为烟雾物理参数反演奠定基础。
</div>
<div class="key-points">
<div class="key-points-title">关键数据与发现</div>
<ul>
<li>细粒度背景分类：将地表分为多类别，每类独立训练距离模型</li>
<li>跨平台一致性：同一方法在MODIS、Sentinel-2、Landsat上均有效</li>
<li>可解释性强：基于物理统计模型，阈值有明确物理意义</li>
<li>为后续烟雾AOD反演、浓度估算提供方法论基础</li>
</ul>
</div>
<div class="author-team">
<div class="author-team-title">🧑‍🏫 作者团队背景</div>
<table class="author-table">
<tr><td class="alabel">团队简介</td><td>中国本土研究团队，以吉林省科技信息服务中心/吉林大学为核心。该团队专注于卫星遥感气溶胶/烟雾的物理反演方法研究，深耕统计与物理模型方向。</td></tr>
<tr><td class="alabel">核心作者</td><td><b>Yehan Sun</b> (第一作者)：从事遥感烟雾检测与光学厚度反演研究，方法学上偏好物理可解释的统计模型；<b>Jun Pan</b> (通信/资深作者)：在卫星遥感数据处理和物理反演算法方向有长期积累。</td></tr>
<tr><td class="alabel">相关积累</td><td>团队长期从事烟雾/气溶胶的物理统计反演方法研究。本文提出的细粒度策略是对传统马氏距离方法的系统改进，是物理模型驱动路线的最新代表。</td></tr>
<tr><td class="alabel">方法论特色</td><td>与同期深度学习路线（其他4篇论文）形成鲜明对比——纯物理统计、跨平台泛化、可解释、面向反演。代表了"检测→反演"技术链的物理端。</td></tr>
</table>
</div>
<div class="insight"><b>对博士论文的启示:</b> 这是2026年最新发表的论文，展示了物理模型与DL结合的新趋势。如果你要从Detection延伸到Retrieval（反演），这是一个很好的起点——物理模型天然支持从检测信号推导物理参数。</div>
</div>

<!-- ====================================================================== -->
<!-- 对比表 -->
<!-- ====================================================================== -->
<div class="table-page">
<h3 class="section">方法对比总览</h3>
<table>
<tr><th>方法</th><th>数据集</th><th>参数量</th><th>F1/mAP</th><th>创新点</th><th>适用场景</th></tr>
<tr><td>VTrUNet</td><td>Landsat-8</td><td>-</td><td>F1>4%提升</td><td>ViT+UNet</td><td>复杂背景分割</td></tr>
<tr><td>Multiattention</td><td>USTC_SmokeRS</td><td>0.7M</td><td>-30%误报</td><td>ViT+CNN交错</td><td>边缘部署</td></tr>
<tr><td>Hybrid CNN-T</td><td>USTC_SmokeRS</td><td>-</td><td>优于基线</td><td>多尺度混合</td><td>通用检测</td></tr>
<tr><td>Land8Fire基准</td><td>Landsat-8</td><td>varies</td><td>F1=96.99%</td><td>数据集构建</td><td>基准测试</td></tr>
<tr><td>Improved MD</td><td>MODIS/Sentinel</td><td>-</td><td>-</td><td>物理模型+DL</td><td>跨平台检测</td></tr>
</table>

<div class="highlight">
<b>关键发现：</b>NIR (B5) + SWIR1 (B6) + SWIR2 (B7) 波段组合在多光谱火烟检测中表现最优。SWIR波段可穿透薄云和烟雾，是火点识别的关键特征。
</div>
</div>

<!-- ====================================================================== -->
<!-- 趋势判断 -->
<!-- ====================================================================== -->
<div class="trend-page">
<h3 class="section">趋势判断与研究建议</h3>

<div class="trend-item">
<h5>1. 多光谱波段选择策略优于全波段堆砌</h5>
<p>Land8Fire和Sen2Fire两项研究一致证实：精选 SWIR+NIR 波段比使用全部波段效果更好。建议在你的模型设计中优先探索波段子集而非全波段输入。</p>
</div>

<div class="trend-item">
<h5>2. Transformer + CNN 混合架构成为主流</h5>
<p>多篇论文验证了 "CNN浅层局部特征 + Transformer深层全局建模" 的混合策略。但融合方式（串联/并行/交错）尚无定论，这是一个有探索价值的方向。</p>
</div>

<div class="trend-item">
<h5>3. 轻量化模型与边缘部署是落地关键</h5>
<p>多注意力交错网络仅 0.7M 参数即可同时保持高精度和实时性。对于实际林火预警系统，参数量控制与精度平衡是核心挑战。</p>
</div>

<div class="trend-item">
<h5>4. 检测→反演的桥接研究开始涌现</h5>
<p>改进马氏距离方法展示了物理模型与深度学习结合的路径，为烟雾参数反演（光学厚度、浓度定量估算）提供方法论基础。这可以是你从 Detection 延伸到 Retrieval 的切入点。</p>
</div>

<div class="trend-item">
<h5>5. USTC_SmokeRS 数据集的持续影响力</h5>
<p>多篇论文以该数据集作为标准基准，说明其在该领域具有持续影响力。建议你在论文中与该数据集上的 SOTA 进行对比。</p>
</div>

<div style="margin-top: 20px; padding: 12px; background: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;">
<h3 style="font-size: 12pt; color: #19375f; margin: 0 0 8px 0;">📊 本周调研总结</h3>
<p>本周共检索5篇野火烟雾检测前沿论文，涵盖3种主流技术路线：</p>
<ul>
<li><b>深度学习路线（4篇）：</b>VTrUNet (Transformer+UNet)、多注意力交错网络 (ViT+CNN)、CNN-Transformer混合、Land8Fire基准。共同趋势：CNN+Transformer混合已成范式。</li>
<li><b>物理模型路线（1篇）：</b>改进马氏距离方法。坚持可解释性，并开始融入细粒度分类策略。</li>
<li><b>数据集建设（1篇）：</b>Land8Fire 20,000+标注样本，波段选择可参考。</li>
</ul>
<p style="margin-top: 6px;"><b>作者团队分布：</b>南澳大学、印度Bennett/IIITDM、密歇根大学安娜堡、阿肯色大学、中国吉林/安徽。覆盖亚、澳、北美、欧洲多国合作网络。</p>
</div>
</div>

</body>
</html>"""

output_path = '/home/vive/Work/Hermes/2026-06-29-weekly-briefing-sample/briefing_week27.pdf'

from weasyprint import HTML as WeasyHTML

WeasyHTML(string=HTML).write_pdf(output_path)

print(f'PDF saved to: {output_path}')
print(f'File size: {os.path.getsize(output_path)} bytes')
