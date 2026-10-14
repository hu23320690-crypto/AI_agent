"""Service-only dynamic prompt; legacy prompt construction is untouched."""
import json

from service_desk.config import ROOT
from utils.prompt_loader import load_report_prompts


def service_prompt(context):
    prompt = (ROOT / 'prompts/service_prompt.txt').read_text(encoding='utf-8')
    prompt = prompt.replace('{business_date}', context['business_date'])
    prompt += '\n当前会话信息：' + json.dumps({
        '业务日期': context['business_date'], '演示用户ID': context.get('user_id') or '未设置',
    }, ensure_ascii=False)
    if context.get('report') and context.get('report_data'):
        prompt += '\n' + load_report_prompts()
        prompt += '\n本轮已查询的报告资料：' + json.dumps(context['report_data'], ensure_ascii=False)
    return prompt


def rag_answer(serialized):
    # Only unwrap a validated service envelope at the existing RAG output path.
    from service_desk.contracts import RagSummarizeResult
    return RagSummarizeResult.model_validate_json(serialized).answer


def report_reference(query, previous_intent, business_date):
    """Supply the business month only for a first relative target request."""
    from utils.report_intent import ReportIntent, _RELATIVE_MONTH, _positive_text, _baseline_month, _COMPARE
    if previous_intent is not None:
        return previous_intent
    positive = _positive_text(query)
    compare = bool(_COMPARE.search(positive))
    if any(not _baseline_month(positive, *match.span(), compare)
           for match in _RELATIVE_MONTH.finditer(positive)):
        return ReportIntent(target_month=business_date[:7])
    return None
