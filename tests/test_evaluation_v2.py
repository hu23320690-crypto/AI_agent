"""Small offline checks for evaluation integrity, not model quality."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from evaluation.metrics import context_metrics, retrieval_metrics
from evaluation.observe import ModelObserver, input_evidence, seed_messages
from evaluation.run import assert_resume_identity, verify_dataset, ROOT
from evaluation.report import summarize, result_sha256, execution_outcome, turn_execution_outcome
from evaluation.compare import compare_cases, comparable, blind_bundle


class EvaluationV2Tests(unittest.TestCase):
    def test_seed_has_completed_pairs_and_no_inference(self):
        spec = {"generator": "synthetic_completed_pairs_v1", "pairs": 64,
                "goal": "处理主刷毛发", "constraints": ["资料不足请拒答"],
                "user_template": "准备记录第 {turn} 轮", "assistant_template": "收到 {turn}",
                "acknowledged": "已记录"}
        messages = seed_messages(spec)
        self.assertEqual(len(messages), 128)
        self.assertEqual(messages[0].content, "处理主刷毛发\n资料不足请拒答")
        self.assertEqual(messages[-2].content, "准备记录第 64 轮")
        self.assertTrue(all(isinstance(m, HumanMessage if i % 2 == 0 else AIMessage)
                            for i, m in enumerate(messages)))
        with self.assertRaises(ValueError):
            seed_messages({**spec, "pairs": True})
        with self.assertRaises(ValueError):
            seed_messages({**spec, "extra": "not frozen"})

    def test_only_context_in_actual_request_counts_after_trimming(self):
        observer = ModelObserver()
        a = Document(page_content="清理主刷之前断开电源。", metadata={"source": "a.txt"})
        b = Document(page_content="充电座应放在平整地面上。", metadata={"source": "b.txt"})
        observer.register_context("whole candidate A+B", [a, b])
        observer.register_context("admitted A", [a])
        response = AIMessage(content="安全清理", response_metadata={"done_reason": "stop"},
                             usage_metadata={"input_tokens": 9, "output_tokens": 3, "total_tokens": 12})
        result = SimpleNamespace(generations=[SimpleNamespace(message=response, generation_info=None)])
        model = SimpleNamespace(model="test", temperature=0)
        captured = []
        def original(actual_model, messages, *args, **kwargs):
            captured.append((actual_model, messages, kwargs))
            return result
        messages = [HumanMessage(content="question\nadmitted A")]
        self.assertIs(observer.record_generate(original, model, messages, tools=[]), result)
        self.assertIs(captured[0][1], messages)
        self.assertEqual(observer.calls[0]["rag_contexts"][0]["docs"][0]["metadata"]["source"], "a.txt")
        self.assertEqual(len(observer.calls[0]["rag_contexts"]), 1)
        self.assertEqual(observer.calls[0]["generations"][0]["message"]["usage_metadata"]["input_tokens"], 9)
        case = {"evidence": [{"source": "data/a.txt", "quote": a.page_content},
                              {"source": "data/b.txt", "quote": b.page_content}], "evidence_policy": "all"}
        metrics = input_evidence(case, observer.calls)["metrics"]
        self.assertTrue(metrics["any_hit"])
        self.assertFalse(metrics["all_required_hit"])
        self.assertFalse(metrics["policy_hit"])

    def test_observation_preserves_exception_and_records_incomplete(self):
        observer = ModelObserver()
        error = ConnectionError("offline failure")
        def failed(*args, **kwargs):
            raise error
        with self.assertRaises(ConnectionError) as caught:
            observer.record_generate(failed, SimpleNamespace(model="test"), [])
        self.assertIs(caught.exception, error)
        self.assertEqual(observer.calls[0]["status"], "error")
        self.assertEqual(observer.calls[0]["error_type"], "ConnectionError")
        result = SimpleNamespace(generations=[SimpleNamespace(
            message=AIMessage(content="cut off", response_metadata={"done_reason": "length"}),
            generation_info=None)])
        observer.record_generate(lambda *a, **k: result, SimpleNamespace(model="test"), [])
        self.assertTrue(observer.calls[-1]["incomplete"])

    def test_resume_rejects_every_reproducibility_dimension(self):
        identity = {"code_sha256": {"a.py": "old"}, "evaluation_sha256": {"run.py": "old"},
                    "dataset_sha256": "old", "source_sha256": {"data.txt": "old"},
                    "model_identity": {"chat": {"digest": "old"}},
                    "dependencies": {"langchain": "old"}, "temperature": 0}
        assert_resume_identity(identity, copy.deepcopy(identity))
        for key in identity:
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, key):
                changed = copy.deepcopy(identity)
                changed[key] = "changed"
                assert_resume_identity(identity, changed)

    def test_multi_evidence_policy_keeps_legacy_any_hit(self):
        case = {"evidence_policy": "all", "evidence": [
            {"source": "data\\a.txt", "quote": "清理主刷之前断开电源。"},
            {"source": "data/b.txt", "quote": "充电座应放在平整地面上。"}]}
        docs = [{"text": case["evidence"][0]["quote"], "metadata": {"source": "C:\\frozen\\a.txt"}}]
        result = retrieval_metrics(case, docs)
        self.assertTrue(result["hit"]["5"])
        self.assertFalse(result["all_required_hit"]["5"])
        self.assertFalse(result["policy_hit"]["5"])
        self.assertEqual(result["required_evidence_coverage"]["5"], [1.0, 0.0])
        docs.append({"text": case["evidence"][1]["quote"], "metadata": {"source": "b.txt"}})
        self.assertTrue(context_metrics(case, docs)["all_required_hit"])
        with self.assertRaises(ValueError):
            retrieval_metrics({"evidence_policy": "implicit"}, docs)

    def test_new_frozen_dataset_and_two_seed_cases_validate(self):
        cases = verify_dataset(ROOT/"evaluation/holdout_v2/cases.jsonl")
        self.assertEqual(len(cases), 40)
        self.assertEqual(sum(bool(c.get("seed_history")) for c in cases), 2)
        self.assertEqual(sum(len(c.get("turns", [])) if c["kind"] == "agent" else 1 for c in cases), 45)

    def test_bound_review_and_planned_denominator_do_not_hide_execution_errors(self):
        cases=[{'id':'K1','kind':'knowledge'},{'id':'K2','kind':'knowledge'},
               {'id':'K3','kind':'knowledge'},{'id':'K4','kind':'knowledge'}]
        rows=[{'id':'K1','mode':'qa','status':'ok','answer':'complete'},
              {'id':'K2','mode':'qa','status':'timeout','answer':'partial'},
              {'id':'K3','mode':'qa','status':'ok','answer':'not yet reviewed'}]
        reviews=[{'id':r['id'],'answer_score':2,'grounded':True,'result_sha256':result_sha256(r)}
                 for r in rows[:2]]
        summary=summarize(cases,rows,{},reviews,True)
        self.assertEqual(summary['knowledge_answers']['strict_pass'],1)
        self.assertEqual(summary['knowledge_answers']['unknown'],3)
        self.assertEqual(summary['knowledge_answers']['strict_pass_fraction_planned'],0.25)
        self.assertEqual(summary['statuses']['not_run'],1)
        with self.assertRaisesRegex(ValueError,'Duplicate|duplicate'):
            summarize(cases,rows,{},[reviews[0],reviews[0]],True)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            summarize(cases,rows,{},[{**reviews[0],'result_sha256':'wrong'}],True)
        with self.assertRaisesRegex(ValueError,'must bind'):
            summarize(cases,rows,{},[{'id':'K1','answer_score':2,'grounded':True}],True)
        with self.assertRaisesRegex(ValueError,'Invalid answer_score'):
            summarize(cases,rows,{},[{**reviews[0],'answer_score':True}],True)

    def test_missing_agent_turn_never_passes_task_or_tool_selection(self):
        case={'id':'A1','kind':'agent','turns':[{'query':'one'},{'query':'two'}]}
        row={'id':'A1','status':'ok','mode':'agent','turns':[
            {'answer':'one','status':'ok','tool_selection':{'pass':True}}]}
        review={'id':'A1','task_pass':True,'result_sha256':result_sha256(row)}
        summary=summarize([case],[row],{},[review],True)
        self.assertEqual(summary['agent']['task_pass'],0)
        self.assertEqual(summary['agent']['tool_selection_pass'],0)
        self.assertEqual(summary['agent']['unknown'],1)

    def test_pairing_and_label_hidden_bundle_preserve_unknown_and_hashes(self):
        cases=[{'id':'K1','kind':'knowledge'},{'id':'K2','kind':'knowledge'}]
        before=[{'id':'K1','status':'ok','answer':'before'}]
        after=[{'id':'K1','status':'ok','answer':'after'},
               {'id':'K2','status':'truncated','answer':'partial'}]
        reviews_before=[{'id':'K1','answer_score':1,'grounded':True,'result_sha256':result_sha256(before[0])}]
        reviews_after=[{'id':'K1','answer_score':2,'grounded':True,'result_sha256':result_sha256(after[0])}]
        transitions=compare_cases(cases,before,after,reviews_before,reviews_after)
        self.assertEqual([t['transition'] for t in transitions],['improved','unknown'])
        bundle,key=blind_bundle(cases,before,after,42)
        self.assertEqual(len(bundle),3)
        self.assertEqual({k['result_sha256'] for k in key},
                         {result_sha256(r) for r in before+after})
        self.assertTrue(all('variant' not in row for row in bundle))
        self.assertEqual(blind_bundle(cases,before,after,42),(bundle,key))
        identity={'identity_version':2,'dataset_sha256':'x','model_identity':{'chat':{'digest':'x'}}}
        comparable(identity,copy.deepcopy(identity))
        with self.assertRaisesRegex(ValueError,'model_identity'):
            comparable(identity,{**identity,'model_identity':{'chat':{'digest':'changed'}}})

    def test_legacy_rag_length_then_complete_planner_is_derived_unknown(self):
        def request(text,incomplete,rag=True):
            return {'status':'ok','incomplete':incomplete,'rag_contexts':[{'docs':[]}] if rag else [],
                    'generations':[{'message':{'content':text,'response_metadata':
                        {'done_reason':'length' if incomplete else 'stop'}}}]}
        case={'id':'A1','kind':'agent','turns':[{'query':'clean'}]}
        row={'id':'A1','mode':'agent','status':'ok','model_requests':[
            request('先断开电源。',True),request('已完成',False,False)],
            'turns':[{'status':'ok','query':'clean','answer':'先断开电源。','model_request_indices':[0,1],
                      'tool_results':[{'name':'rag_summarize','status':'success','content':'先断开电源。'}],
                      'tool_selection':{'pass':True}}]}
        review={'id':'A1','task_pass':True,'result_sha256':result_sha256(row)}
        self.assertEqual(execution_outcome(row),'truncated')
        summary=summarize([case],[row],{},[review],True)
        self.assertEqual(summary['statuses']['ok'],1)
        self.assertEqual(summary['execution_outcomes']['truncated'],1)
        self.assertEqual(summary['agent']['task_pass'],0)
        self.assertEqual(summary['agent']['unknown'],1)
        # An optional summary truncation must not invalidate a successful task.
        row['model_requests'][0]=request('摘要未完成',True,False)
        self.assertEqual(execution_outcome(row),'ok')
        # A completed retry can supersede an identical earlier partial output.
        row['model_requests']=[request('先断开电源。',True),request('先断开电源。',False)]
        self.assertEqual(execution_outcome(row),'ok')

    @staticmethod
    def legacy_unused_planner_row():
        def request(text,incomplete,rag):
            return {'status':'ok','incomplete':incomplete,
                    'rag_contexts':[{'docs':[]}] if rag else [],
                    'generations':[{'message':{'content':text,'response_metadata':
                        {'done_reason':'length' if incomplete else 'stop'}}}]}
        answer='先断开电源，再清理主刷。'
        return {'id':'A1','mode':'agent','status':'truncated','model_requests':[
            request(answer,False,True),request('未交付的规划文本',True,False)],
            'turns':[{'status':'truncated','query':'clean','answer':answer,
                'model_request_indices':[0,1],
                'tool_results':[{'name':'rag_summarize','status':'success','content':answer}],
                'tool_selection':{'pass':True}}]}

    def test_complete_delivered_rag_survives_unused_planner_truncation(self):
        case={'id':'A1','kind':'agent','turns':[{'query':'clean'}]}
        row=self.legacy_unused_planner_row()
        original=copy.deepcopy(row)
        review={'id':'A1','task_pass':True,'result_sha256':result_sha256(row)}
        summary=summarize([case],[row],{},[review],True)
        self.assertEqual(summary['statuses']['truncated'],1)
        self.assertEqual(summary['execution_outcomes']['ok'],1)
        self.assertEqual(summary['agent']['task_pass'],1)
        self.assertEqual(summary['agent']['tool_selection_pass'],1)
        self.assertEqual(summary['agent']['unknown'],0)
        self.assertEqual(turn_execution_outcome(row['turns'][0],row),'ok')
        bundle,key=blind_bundle([case],[row],[],42)
        self.assertEqual(bundle[0]['raw_status'],'truncated')
        self.assertEqual(bundle[0]['execution_status'],'ok')
        self.assertEqual(bundle[0]['turn_execution_outcomes'],[
            {'turn_index':1,'raw_status':'truncated','execution_status':'ok'}])
        self.assertEqual(key[0]['result_sha256'],review['result_sha256'])
        self.assertEqual(row,original)
        self.assertEqual(compare_cases([case],[row],[row],[review],[review])[0]['transition'],'stable_pass')

    def test_returned_rag_truncation_and_current_rejection_stay_unknown(self):
        case={'id':'A1','kind':'agent','turns':[{'query':'clean'}]}
        for rejection in ('returned_rag','current_exception'):
            with self.subTest(rejection=rejection):
                row=self.legacy_unused_planner_row()
                if rejection=='returned_rag':
                    row['model_requests'][0]['incomplete']=True
                    row['model_requests'][0]['generations'][0]['message']['response_metadata']['done_reason']='length'
                else:
                    row['error_type']='IncompleteModelOutput'
                    row['error']='当前版本拒绝截断'
                    row['turns'][0].update(error_type='IncompleteModelOutput',error='当前版本拒绝截断')
                review={'id':'A1','task_pass':True,'result_sha256':result_sha256(row)}
                summary=summarize([case],[row],{},[review],True)
                self.assertEqual(execution_outcome(row),'truncated')
                self.assertEqual(summary['agent']['task_pass'],0)
                self.assertEqual(summary['agent']['tool_selection_pass'],0)
                self.assertEqual(summary['agent']['unknown'],1)

    def test_planner_correction_requires_exact_complete_delivery_evidence(self):
        for change in ('answer','tool_status','missing_generation','missing_indices','planner_is_rag'):
            with self.subTest(change=change):
                row=self.legacy_unused_planner_row()
                if change=='answer':
                    row['turns'][0]['answer']='planner实际生成的部分答案'
                elif change=='tool_status':
                    row['turns'][0]['tool_results'][0]['status']='error'
                elif change=='missing_generation':
                    row['model_requests'][0]['generations']=[]
                elif change=='missing_indices':
                    row['turns'][0]['model_request_indices']=[1]
                else:
                    row['model_requests'][-1]['rag_contexts']=[{'docs':[]}]
                self.assertEqual(execution_outcome(row),'truncated')

    def test_corrected_turn_cannot_hide_a_missing_later_turn(self):
        case={'id':'A1','kind':'agent','turns':[{'query':'clean'},{'query':'follow up'}]}
        row=self.legacy_unused_planner_row()
        review={'id':'A1','task_pass':True,'result_sha256':result_sha256(row)}
        summary=summarize([case],[row],{},[review],True)
        self.assertEqual(summary['agent']['task_pass'],0)
        self.assertEqual(summary['agent']['tool_selection_pass'],0)
        self.assertEqual(summary['agent']['unknown'],1)
        # A collected second turn that actually returned partial RAG text also
        # remains incomplete even when the first turn's planner flag is corrected.
        partial=copy.deepcopy(row['model_requests'][0])
        partial['incomplete']=True
        partial['generations'][0]['message']['content']='部分第二轮答案'
        partial['generations'][0]['message']['response_metadata']['done_reason']='length'
        row['model_requests'].append(partial)
        row['turns'].append({'status':'ok','query':'follow up','answer':'部分第二轮答案',
            'model_request_indices':[2],'tool_selection':{'pass':True},
            'tool_results':[{'name':'rag_summarize','status':'success','content':'部分第二轮答案'}]})
        review['result_sha256']=result_sha256(row)
        summary=summarize([case],[row],{},[review],True)
        self.assertEqual(execution_outcome(row),'truncated')
        self.assertEqual(summary['agent']['task_pass'],0)
        self.assertEqual(summary['agent']['unknown'],1)

    def test_installed_hook_observes_real_format_boundary_without_model_io(self):
        from langchain_ollama import ChatOllama
        result=SimpleNamespace(generations=[SimpleNamespace(message=AIMessage(content='observed'),generation_info=None)])
        def offline_generate(model,messages,*args,**kwargs):
            return result
        with patch('urllib.request.urlopen',side_effect=RuntimeError('offline test forbids network')):
            from rag.rag_service import RagSummarizeService
            observer=ModelObserver()
            original_format=RagSummarizeService.format_context
            with patch.object(ChatOllama,'_generate',offline_generate):
                with observer.installed():
                    doc=Document(page_content='清理主刷之前断开电源。',metadata={'source':'a.txt'})
                    formatted=RagSummarizeService.format_context([doc])
                    model=ChatOllama(model='offline-placeholder',temperature=0)
                    self.assertIs(model._generate([HumanMessage(content=formatted)]),result)
            self.assertIs(RagSummarizeService.format_context,original_format)
        self.assertEqual(len(observer.calls),1)
        self.assertEqual(observer.calls[0]['rag_contexts'][0]['docs'][0]['text'],doc.page_content)


if __name__ == "__main__":
    unittest.main()
