from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "research" / "weekly-briefing-v2" / "scripts" / "run_weekly_e2e.py"
SPEC = importlib.util.spec_from_file_location("weekly_runner", RUNNER)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runner)


class ReportRendererTests(unittest.TestCase):
    def sample_papers(self):
        return [
            {
                "title": "A Multimodal Foundation Model for Wildfire Smoke Mapping",
                "url": "https://arxiv.org/abs/2609.01234",
                "arxiv_id": "2609.01234",
                "source": "arxiv_api",
                "published": "2026",
                "authors": ["Lin Chen", "Mei Wang", "A. Rivera"],
                "abstract": "We combine multispectral satellite observations with temporal priors to map wildfire smoke while reporting uncertainty and cross-region transfer performance.",
                "team_profile": {
                    "institutions": ["Example Remote Sensing Laboratory", "Example Climate Institute"],
                    "work_topics": ["Remote Sensing", "Wildfire", "Computer Vision"],
                    "authors": [
                        {"name": "Lin Chen", "works_count": 84, "cited_by_count": 2310, "h_index": 21, "topics": ["Remote Sensing", "Wildfire"], "openalex": "https://openalex.org/A123", "recent_works": [{"title": "Smoke Transport", "year": "2025", "url": "https://doi.org/10.1000/smoke"}]},
                        {"name": "Mei Wang", "works_count": 52, "cited_by_count": 1190, "h_index": 16, "topics": ["Computer Vision", "Earth Observation"]},
                    ],
                },
                "analysis": {
                    "problem": "如何在跨地区、跨传感器条件下稳定识别山火烟羽，并显式报告不确定性？",
                    "why_it_matters": "它把时序先验与多光谱表征放到同一条可验证流程中，直接对应业务中的域偏移与漏检风险。",
                    "method_steps": [
                        {"name": "多源对齐", "detail": "统一不同卫星的空间分辨率、时间窗口和光谱通道。"},
                        {"name": "时空编码", "detail": "用基础模型提取烟羽纹理，并用时序先验约束传播方向。"},
                        {"name": "不确定性校准", "detail": "区分模型不确定性与标签歧义，输出像素级置信度。"},
                    ],
                    "evidence": ["跨区域测试保持主要指标稳定。", "消融实验显示时序先验改善薄烟识别。"],
                    "comparison": [
                        {"dimension": "跨区域泛化", "paper": "显式跨域评估", "baseline": "以单区域随机划分为主"},
                        {"dimension": "可信度", "paper": "提供校准误差", "baseline": "只报告分割精度"},
                    ],
                    "limitations": ["极薄烟与云边界仍容易混淆。", "需要核验训练数据的地区覆盖。"],
                },
            },
            {
                "title": "Uncertainty-Aware Cross-Sensor Smoke Segmentation",
                "doi": "10.1000/example.2026.42",
                "url": "https://doi.org/10.1000/example.2026.42",
                "source": "crossref_api",
                "published": "2026",
                "authors": ["Sara Kim", "N. Patel"],
                "abstract": "A calibrated segmentation pipeline aligns geostationary and polar-orbiting imagery and separates model uncertainty from label ambiguity.",
                "team_profile": {
                    "institutions": ["Example University"],
                    "work_topics": ["Image Segmentation", "Uncertainty", "Satellite Imagery"],
                    "authors": [
                        {"name": "Sara Kim", "works_count": 37, "cited_by_count": 760, "h_index": 13, "topics": ["Uncertainty", "Earth Observation"]},
                    ],
                },
                "analysis": {
                    "problem": "如何在传感器差异明显时保持烟雾分割结果可校准？",
                    "why_it_matters": "它把跨传感器对齐和置信度校准拆开评估，便于判断性能提升究竟来自哪里。",
                    "method_steps": [
                        {"name": "传感器对齐", "detail": "学习共享表征并保留各传感器特有信息。"},
                        {"name": "分割预测", "detail": "以共享解码器输出烟雾区域。"},
                        {"name": "校准验证", "detail": "按地区和传感器分别报告可靠性曲线。"},
                    ],
                    "evidence": ["在两个跨传感器测试集上报告完整消融。"],
                    "comparison": [{"dimension": "校准", "paper": "分组可靠性评估", "baseline": "总体平均置信度"}],
                    "limitations": ["尚未覆盖极端沙尘与烟雾混合场景。"],
                },
            },
        ]

    def test_fixed_focus_does_not_consume_profile_by_default(self):
        queries = runner.build_queries(
            {"research": {"core_keywords": ["wildfire smoke"]}},
            {"topic_weights": {"drifting generated topic": 99}},
            {"biases": [{"source": "report", "direction": "boost", "topic": "self feedback"}]},
        )
        self.assertIn("wildfire smoke", queries)
        self.assertNotIn("drifting generated topic", queries)
        self.assertNotIn("self feedback", queries)

    def test_html_and_pdf_keep_original_links(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            papers = self.sample_papers()
            stats = {"selected_count": 2, "raw_candidates": 18, "cross_week_deduped": 4}
            queries = ["wildfire smoke satellite segmentation", "multispectral smoke detection"]
            markdown = runner.make_report("2026-W38", papers, stats, target, queries)
            html_path = target / "report.html"
            html_text = runner.make_report_html("2026-W38", papers, stats, queries, html_path)
            pdf_path = target / "report.pdf"
            runner.make_pdf(html_text, markdown, pdf_path)
            self.assertTrue(pdf_path.is_file())
            self.assertGreater(pdf_path.stat().st_size, 5000)
            self.assertIn("https://arxiv.org/abs/2609.01234", html_text)
            self.assertIn("https://openalex.org/A123", html_text)
            self.assertIn("https://doi.org/10.1000/smoke", html_text)
            self.assertIn("跨论文方法与证据对比", html_text)
            self.assertNotIn("weixin", html_text.lower())


if __name__ == "__main__":
    unittest.main()
