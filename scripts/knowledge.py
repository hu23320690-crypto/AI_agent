"""Local administrator CLI; none of these operations is exposed to the Agent."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))


def catalog():
    from rag.security import SourceCatalog
    from utils.config_hander import chroma_conf
    from utils.path_tool import get_abs_path
    return SourceCatalog(get_abs_path(chroma_conf['data_path']),
                         get_abs_path(chroma_conf['source_catalog']),
                         policy_path=get_abs_path(chroma_conf['security_policy']))


def main(argv=None):
    parser = argparse.ArgumentParser(description='知识来源管理员：扫描隔离、审核、撤销、索引同步')
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('scan', help='将新增/变化文件登记为隔离，打印摘要，不批准')
    commands.add_parser('status', help='只读查看当前允许和被隔离的来源')
    p = commands.add_parser('approve', help='审核明确的文件 SHA256，随后需 sync 入库')
    p.add_argument('path', help='相对于 data 的 TXT/PDF 路径')
    p.add_argument('--sha256', required=True, help='scan 输出中人工核对过的文件 SHA256')
    p.add_argument('--reason', required=True, help='审核依据；仅用于管理员记录')
    p.add_argument('--demo', action='store_true', help='标记演示允许源，不声称厂商核验')
    p.add_argument('--allow-risk', action='store_true', help='明确复核并允许规则命中的合法引用')
    p = commands.add_parser('revoke', help='立即阻止该来源未来检索；sync 可物理清理索引')
    p.add_argument('source_id')
    p.add_argument('--reason', required=True)
    commands.add_parser('sync', help='同步当前允许来源，删除无效/撤销版本的分块')
    args = parser.parse_args(argv)
    try:
        if args.operation == 'sync':
            from rag.vector_store import VectorStoreService
            result = VectorStoreService().load_document()
        else:
            sources = catalog()
            if args.operation == 'scan':
                result = sources.scan()
            elif args.operation == 'status':
                snapshot = sources.snapshot()
                result = {'allowed': list(snapshot.authorized.values()), 'blocked': snapshot.blocked,
                          'stamp': snapshot.stamp}
            elif args.operation == 'approve':
                result = sources.approve(args.path, expected_sha256=args.sha256, reason=args.reason,
                                         status='demo_allowed' if args.demo else 'approved',
                                         allow_risk=args.allow_risk)
            else:
                result = sources.revoke(args.source_id, reason=args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return int(isinstance(result, dict) and bool(result.get('failed')))
    except Exception as exc:
        # Policy errors carry only codes, never document text.
        from rag.security import KnowledgeAccessError
        code = exc.code if isinstance(exc, KnowledgeAccessError) else type(exc).__name__
        print(json.dumps({'ok': False, 'reason': code}, ensure_ascii=False), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
