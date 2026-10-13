"""Conservative response boundary for guarantees under changed prerequisites.

This is an application policy, not an entailment solver. A knowledge-only
service cannot promise a device's outcome when the user removes a condition.
It deliberately favors uncertainty over an unsupported operational guarantee.
"""
import re
from rag.hybrid import tokenize


_GUARANTEE = re.compile(r'保证|确保')
_CHANGED_CONDITION = re.compile(r'断开|关闭|不满足|不具备|未连接|未设置|没有|离线|没网|前提改变|条件改变')
CONDITIONAL_GUARANTEE_REPLY = (
    '不能据此保证前提改变后仍照常执行。原结论受适用条件限制，'
    '不能直接沿用到条件改变后的情景；目前无法确认所问情况下的执行结果。'
)


def missing_individual_lifetime_reply(question, docs):
    """Decline a quantitative individual prognosis without individual evidence.

    A generic replacement interval is not a measured remaining lifetime. This
    rule does not diagnose damage or invent an immediate-failure explanation.
    Actual individual remaining-life observations keep the generative route.
    """
    if (not isinstance(question, str)
            or not re.search(r'预测|准确|精确|估算', question)
            or not re.search(r'这(?:片|个|块|台)|该|一片|我的|它', question)
            or not re.search(r'剩余|剩下|还能', question)
            or not re.search(r'寿命|失效|多少[^，。？?]{0,12}(?:小时|分钟|天)', question)):
        return None
    # A concrete observation or explicit predictive relationship is materially
    # different from a routine interval. Do not replace such evidence by a
    # blanket refusal; generation must check its entity and conditions.
    if any(re.search(r'(?:实测|检测结果|剩余寿命|寿命预测模型|失效预测模型)[^。\n]{0,100}'
                     r'(?:\d|计算|公式)', document.page_content) for document in docs):
        return None
    return ('当前提供的信息不足以准确预测该部件的剩余连续使用时长或失效时间。'
            '常规维护和更换周期不能当作这个部件的实测剩余寿命。')


def requires_conditional_guarantee(question):
    return isinstance(question, str) and bool(_GUARANTEE.search(question) and
                                             _CHANGED_CONDITION.search(question))


def missing_named_manufacturer_reply(question, docs):
    """Decline a specific quoted product's factory value absent from evidence.

    This is a conservative missing-entity check, not verification that a
    mentioned product's specifications are correct. It deliberately covers
    explicit quoted names only; it does not infer product identities.
    """
    if (not isinstance(question, str) or not re.search(r'厂商|厂家|制造商', question)
            or not re.search(r'比例|参数|规格|扭矩|标准|型号|版本|数值|浓度|电压|电流', question)):
        return None
    names = [next(value for value in match if value) for match in re.findall(
        r'“([^”\n]{2,80})”|「([^」\n]{2,80})」|"([^"\n]{2,80})"|\'([^\'\n]{2,80})\'', question)]
    names = [name for name in names if re.search(r'[A-Za-z\u4e00-\u9fff]', name)]
    if not names:
        return None
    compact = lambda value: re.sub(r'\s+', '', value).casefold()
    corpus = [compact(document.page_content) for document in docs]
    missing = [name for name in names if not any(compact(name) in text for text in corpus)]
    if not missing:
        return None
    return ('当前提供的资料中没有找到' + '、'.join('「' + name + '」' for name in missing)
            + '的对应依据，无法确认所问产品的厂家参数或唯一准确值。通用说明不能作为该产品的厂家标准。')


def conditional_guarantee_reply(question, docs):
    """Keep the changed scenario and relevant prerequisite text distinguishable.

    Quotes are evidence, not a proof that a prerequisite is necessary. Do not
    infer either success or failure after a condition changes. Names and facts
    come from the original request and caller-validated references only.
    """
    terms = set(tokenize(question))
    candidates = {}
    for document in docs:
        for sentence in re.findall(r'[^。！？\n]+[。！？]', document.page_content):
            sentence = sentence.strip().lstrip('- ').strip()
            if (len(sentence) <= 700 and re.search(r'只要|前提|条件是|条件下', sentence)):
                common = terms.intersection(tokenize(sentence))
                if len(common) >= 2:
                    candidates[sentence] = len(common)
    quotes = sorted(candidates, key=lambda text: (-candidates[text], text))[:2]
    request = question if len(question) <= 400 else question[:400] + '（原问题引用节选）'
    reply = CONDITIONAL_GUARANTEE_REPLY + '\n\n当前追问：' + request
    if quotes:
        reply += '\n\n以下资料片段提到了条件，不能据此保证前提改变后的结果：\n'
        reply += '\n'.join('「' + quote + '」' for quote in quotes)
    return reply
