"""Report selection and arithmetic use user intent and verified facts only."""
import unittest

from utils.report_intent import ReportIntent, resolve_report_intent, shift_month
from utils.report_render import render_lookup


def record(month='2032-11', *, user='demo', efficiency='覆盖率:83.5%\\n日均清扫:31㎡',
           consumables='滤网寿命:剩余45天\\n集尘袋消耗:1.3个/月'):
    return {'status': 'ok', 'user_id': user, 'month': month, 'data': {
        '特征': '70㎡公寓 | 木地板', '效率': efficiency,
        '耗材': consumables, '对比': '不参与字段选择的比较说明'}}


class ReportIntentTests(unittest.TestCase):
    def test_selects_requested_fields_in_request_order_with_display_modifiers(self):
        result = record(efficiency='跨楼层失败:3次/周\\n玩具避障率:72%')
        text = render_lookup(result, query='请查2032年11月，只列跨楼层失败频次、玩具避障率和集尘袋每月消耗。')
        for expected in ('跨楼层失败：3次/周', '玩具避障率：72%', '集尘袋消耗：1.3个/月'):
            self.assertIn(expected, text)
        for unrelated in ('70㎡', '滤网寿命', '使用对比', '木地板'):
            self.assertNotIn(unrelated, text)
        self.assertLess(text.index('跨楼层失败'), text.index('玩具避障率'))

    def test_next_month_retains_fields_and_computes_percentage_points(self):
        before = record()
        after = record('2032-12', efficiency='覆盖率:84.2%\\n日均清扫:33㎡')
        query = '那下一月这两个数各是多少？与刚才相比分别增加了多少？'
        text = render_lookup(after, query=query,
                             previous_queries=['请查2032年11月的覆盖率和日均清扫面积，只需要这两个数。'],
                             lookup_results=[before])
        self.assertIn('2032-12 与 2032-11', text)
        self.assertIn('增加0.7个百分点', text)
        self.assertIn('增加2㎡', text)
        self.assertNotIn('增加0.7%', text)
        self.assertNotIn('滤网寿命', text)

    def test_explicit_new_fields_replace_previous_fields(self):
        text = render_lookup(record('2032-12'), query='2032年12月只列集尘袋消耗',
                             previous_queries=['2032年11月只列覆盖率和日均清扫'])
        self.assertIn('集尘袋消耗', text)
        self.assertNotIn('覆盖率', text)

    def test_complete_report_clears_previous_field_limit(self):
        text = render_lookup(record(), query='请给2032年11月完整报告，包括覆盖率',
                             previous_queries=['只列覆盖率'])
        self.assertIn('使用概况', text)
        self.assertIn('滤网寿命', text)

    def test_unrecognized_and_missing_fields_do_not_expand_to_full_report(self):
        for query in ('2032年11月只列电量', '2032年11月只列覆盖率和电量', '2032年11月只回答覆盖率和电量'):
            with self.subTest(query=query):
                text = render_lookup(record(), query=query)
                self.assertIn('电量：未提供', text)
                self.assertNotIn('使用概况', text)
                self.assertNotIn('滤网寿命', text)
        text = render_lookup(record(), query='只需要这三个指标')
        self.assertIn('无法识别', text)
        self.assertNotIn('使用概况', text)

    def test_last_explicit_scope_request_wins(self):
        limited = render_lookup(record(), query='生成完整报告，但只列覆盖率')
        self.assertIn('覆盖率', limited)
        self.assertNotIn('使用概况', limited)
        complete = render_lookup(record(), query='只列覆盖率，改为完整报告')
        self.assertIn('使用概况', complete)

    def test_negative_field_clause_is_not_selected(self):
        text = render_lookup(record(), query='只列覆盖率，不要日均清扫和滤网寿命')
        self.assertIn('覆盖率', text)
        self.assertNotIn('日均清扫', text)
        self.assertNotIn('滤网寿命', text)

    def test_plain_metric_list_keeps_unknown_fields_in_both_orders(self):
        queries = ('查2032年11月覆盖率和电量',
                   '查2032年11月电量和覆盖率',
                   '覆盖率和电量是多少',
                   '请查询2032年11月的覆盖率、日均清扫面积以及电量各是多少')
        for query in queries:
            with self.subTest(query=query):
                text = render_lookup(record(), query=query)
                self.assertIn('覆盖率：83.5%', text)
                self.assertIn('电量：未提供', text)
                self.assertNotIn('使用概况', text)
                self.assertNotIn('滤网寿命', text)
                if query.index('电量') < query.index('覆盖率'):
                    self.assertLess(text.index('电量'), text.index('覆盖率'))

    def test_unknown_plain_list_replaces_prior_known_field_limit(self):
        intent = resolve_report_intent('电量和温度是多少', ['只列覆盖率和日均清扫'],
                                       known_fields=['覆盖率', '日均清扫'])
        self.assertEqual(intent.fields, ('电量', '温度'))
        text = render_lookup(record(), intent=intent)
        self.assertIn('电量：未提供', text)
        self.assertIn('温度：未提供', text)
        self.assertNotIn('覆盖率', text)

    def test_plain_list_does_not_guess_comparison_negation_or_report_prose(self):
        cases = [('2032年11月覆盖率与2032年10月相比增加多少', ('覆盖率',)),
                 ('查2032年11月覆盖率，不要电量和温度', ('覆盖率',)),
                 ('完整报告，包括覆盖率和电量', ()),
                 ('覆盖率怎么样和有没有电量', ('覆盖率',))]
        for query, expected in cases:
            with self.subTest(query=query):
                intent = resolve_report_intent(query, known_fields=['覆盖率', '日均清扫'])
                self.assertEqual(intent.fields, expected)

    def test_wrong_month_never_uses_available_record(self):
        text = render_lookup(record(), query='查2033年1月覆盖率')
        self.assertIn('2033-01', text)
        self.assertIn('不能用其他月份', text)
        self.assertNotIn('83.5%', text)

    def test_invalid_explicit_month_does_not_fall_back(self):
        for query in ('2032-13只列覆盖率', '2032年0月覆盖率'):
            with self.subTest(query=query):
                text = render_lookup(record(), query=query)
                self.assertIn('月份无效', text)
                self.assertNotIn('83.5%', text)

    def test_not_found_and_missing_baseline_never_become_zero(self):
        missing = {'status': 'not_found', 'user_id': 'demo', 'month': '2032-10'}
        intent = ReportIntent(fields=('覆盖率',), target_month='2032-11',
                              comparison_month='2032-10', compare=True, limited=True)
        for results in ([], [missing]):
            with self.subTest(results=results):
                text = render_lookup(record(), intent=intent, lookup_results=results)
                self.assertIn('83.5%', text)
                self.assertIn('无法计算变化', text)
                self.assertNotIn('增加83.5', text)
        self.assertIn('未找到', render_lookup(missing))

    def test_other_identity_cannot_supply_comparison_baseline(self):
        text = render_lookup(record(), query='2032年11月覆盖率与2032年10月相比',
                             lookup_results=[record('2032-10', user='someone-else')])
        self.assertIn('未查询到', text)
        self.assertIn('无法计算变化', text)
        self.assertNotIn('| 指标 |', text)

    def test_differences_handle_decreases_zero_units_and_qualifiers(self):
        cases = [('83.5%', '80%', '减少3.5个百分点'),
                 ('31㎡', '31㎡', '不变：0㎡'),
                 ('1.3个/月', '1.1个/月', '减少0.2个/月'),
                 ('3次/周', '3次/月', '记录单位不同'),
                 ('剩余45天', '剩余40天', '减少5天'),
                 ('预计剩余45天', '剩余40天', '不是单一可比数值')]
        for before, after, expected in cases:
            with self.subTest(before=before, after=after):
                old = record('2032-10', efficiency='指标甲:' + before)
                new = record(efficiency='指标甲:' + after)
                intent = ReportIntent(fields=('指标甲',), target_month='2032-11',
                                      comparison_month='2032-10', compare=True)
                self.assertIn(expected, render_lookup(new, intent=intent, lookup_results=[old]))

    def test_explicit_month_comparison_and_year_rollover(self):
        intent = resolve_report_intent('比较2032年11月和12月的覆盖率', known_fields=['覆盖率'])
        self.assertEqual((intent.target_month, intent.comparison_month), ('2032-12', '2032-11'))
        intent = resolve_report_intent('下一月覆盖率', ['2032年12月覆盖率'], known_fields=['覆盖率'])
        self.assertEqual(intent.target_month, '2033-01')
        self.assertEqual(shift_month('2032-01', -1), '2031-12')

    def test_latest_relative_month_advances_across_multiple_turns(self):
        intent = resolve_report_intent('那下一月这两个数呢',
                                       ['2032年10月只列覆盖率和日均清扫', '那下一月这两个数呢'],
                                       known_fields=['覆盖率', '日均清扫'])
        self.assertEqual(intent.target_month, '2032-12')
        self.assertEqual(intent.fields, ('覆盖率', '日均清扫'))

    def test_metric_catalog_is_discovered_from_verified_data_not_gold_values(self):
        result = record(efficiency='新指标乙:2次/月', consumables='新指标丙:3个/月')
        text = render_lookup(result, query='2032年11月只列新指标丙和新指标乙')
        self.assertIn('新指标丙：3个/月', text)
        self.assertIn('新指标乙：2次/月', text)
        self.assertNotIn('使用概况', text)


if __name__ == '__main__':
    unittest.main()
