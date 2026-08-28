"""Deterministic AI Mock Engine used until a real LLM provider is configured."""
from __future__ import annotations

import re
from typing import Any

RISK_PATTERNS = {
    "critical": ("chuyển tiền trước", "không hoàn cọc", "phạt tiền", "giữ căn cước", "thu hồi nợ"),
    "high": ("tăng giá tùy ý", "lãi suất điều chỉnh", "phí ẩn", "tịch thu", "thử việc không lương"),
    "medium": ("đặt cọc", "phí môi giới", "phạt trả trước", "bảo hiểm", "làm thêm"),
}

def ai_analyze_contract_context(contract_text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a predictable semantic-style risk report for UI/integration tests.

    This is intentionally local and deterministic. It does not claim to be a
    legal opinion and can later be replaced by an OpenAI/Gemini adapter.
    """
    context = f"{contract_text or ''} {metadata or {}}".lower()
    findings: list[dict[str, Any]] = []
    weights = {"critical": 35, "high": 20, "medium": 8}
    for level, patterns in RISK_PATTERNS.items():
        for pattern in patterns:
            if re.search(re.escape(pattern), context):
                findings.append({"risk_level": level, "matched_term": pattern, "warning": f"Phát hiện nội dung cần rà soát: {pattern}."})
    score = min(100.0, round(sum(weights[item["risk_level"]] for item in findings), 2))
    if score >= 70: label = "Rủi ro cao"
    elif score >= 35: label = "Rủi ro trung bình-cao"
    elif score > 0: label = "Cần rà soát thêm"
    else: label = "Chưa phát hiện dấu hiệu nổi bật"
    return {"risk_score": score, "risk_label": label, "ai_overview": f"AI Mock Engine: {label}. Báo cáo tự động chỉ mang tính tham khảo, không thay thế tư vấn pháp lý.", "ai_findings": findings}
