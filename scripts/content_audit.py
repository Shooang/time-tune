#!/usr/bin/env python3
import json
import re
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SENSITIVE_DIR = PROJECT_ROOT / "docs" / "content" / "sensitive"
LOG_DIR = SCRIPT_DIR / "audit_logs"

LEVEL_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}
LEVEL_NAMES = {1: "🔴 一级黑词", 2: "🟠 二级红词", 3: "🟡 三级黄词"}
RESULT_NAMES = {"PASS": "✅ 通过", "WARN": "⚠️ 警告", "FAIL": "❌ 不通过"}


class ContentAuditor:
    def __init__(self):
        self.words = []
        self.events = []
        self.positive_phrases = []
        self._load_data()

    def _load_data(self):
        words_path = SENSITIVE_DIR / "sensitive-words.json"
        events_path = SENSITIVE_DIR / "sensitive-events.json"

        if words_path.exists():
            with open(words_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.words = data.get("words", [])
                self.positive_phrases = data.get("positive_phrases", [])

        if events_path.exists():
            with open(events_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.events = data.get("events", [])

    def audit_text(self, text: str, context: Optional[Dict] = None) -> Dict:
        if context is None:
            context = {}

        year = context.get("year")
        hits = []
        result = "PASS"

        for word_entry in self.words:
            word = word_entry["word"]
            level = word_entry["level"]
            pattern = re.escape(word)
            matches = list(re.finditer(pattern, text))

            for match in matches:
                start, end = match.span()
                context_start = max(0, start - 20)
                context_end = min(len(text), end + 20)
                context_text = text[context_start:context_end]

                allowed = word_entry.get("allowed_context", "")
                violation = False

                if level == 1:
                    violation = True
                    result = "FAIL"
                elif level == 2:
                    if allowed and self._check_context(word, allowed, context):
                        pass
                    else:
                        violation = True
                        if result != "FAIL":
                            result = "WARN"
                elif level == 3:
                    if allowed and not self._check_context_loose(word, allowed, context):
                        violation = True
                        if result == "PASS":
                            result = "WARN"

                if violation:
                    hits.append({
                        "word": word,
                        "level": level,
                        "category": word_entry.get("category", ""),
                        "position": start,
                        "context": context_text,
                        "replacement": word_entry.get("replacement", ""),
                        "note": word_entry.get("note", ""),
                        "allowed_context": allowed
                    })

        event_hits = self._check_events(text, context)
        hits.extend(event_hits)
        if event_hits:
            for eh in event_hits:
                if eh["level"] in ("C", "D", "E"):
                    result = "FAIL"
                elif eh["level"] == "B" and result == "PASS":
                    result = "WARN"

        return {
            "result": result,
            "hits": hits,
            "word_count": len(text),
            "hit_count": len(hits),
            "level1_count": len([h for h in hits if h.get("level") == 1]),
            "level2_count": len([h for h in hits if h.get("level") == 2]),
            "level3_count": len([h for h in hits if h.get("level") == 3]),
            "timestamp": datetime.now().isoformat()
        }

    def _check_context(self, word: str, allowed: str, context: Dict) -> bool:
        year = context.get("year")
        if year is None:
            return False

        year = int(year)

        if "1950-1971" in allowed or "1950-1960" in allowed:
            if year < 1950 or year > 1971:
                return False
        if "1972年" in allowed and "禁用" in allowed:
            if year >= 1972:
                return False
        if "1960-1980" in allowed:
            if year < 1960 or year > 1989:
                return False
        if "1976年10月后" in allowed:
            if year < 1977:
                return False
        if "1978年后" in allowed:
            if year < 1978:
                return False
        if "80年代" in allowed:
            if year < 1980:
                return False
        if "60-70年代" in allowed or "60-70年代" in allowed:
            if year < 1960 or year > 1979:
                return False
        if "全时段" in allowed or "全时段正面" in allowed or "正面" in allowed:
            return True
        if "抗美援朝" in allowed and str(year) in ["1950", "1951", "1952", "1953"]:
            return True
        if "引用" in allowed and "当时报道" in allowed:
            return True
        if "正面报道" in allowed or "正面语境" in allowed or "官方语境" in allowed:
            return True

        return False

    def _check_context_loose(self, word: str, allowed: str, context: Dict) -> bool:
        return True

    def _check_events(self, text: str, context: Dict) -> List[Dict]:
        hits = []
        year = context.get("year")
        if year is None:
            return hits
        year = int(year)

        for event in self.events:
            forbidden = event.get("forbidden_phrases", [])
            for phrase in forbidden:
                if phrase and phrase in text:
                    hits.append({
                        "word": phrase,
                        "level": event["level"],
                        "category": f"敏感事件：{event['name']}",
                        "position": text.find(phrase),
                        "context": text[max(0, text.find(phrase)-20):text.find(phrase)+len(phrase)+20],
                        "replacement": "，".join(event.get("allowed_phrases", [])[:2]),
                        "note": event.get("official_narrative", ""),
                        "event_id": event["id"],
                        "event_name": event["name"],
                        "event_level": event["level"]
                    })
        return hits

    def audit_file(self, file_path: Path, context: Optional[Dict] = None) -> Dict:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        if context is None:
            context = {}

        result = self.audit_text(text, context)
        result["file_path"] = str(file_path)
        return result

    def audit_directory(self, dir_path: Path, pattern: str = "*.md", exclude_dirs: Optional[List[str]] = None) -> List[Dict]:
        results = []
        if exclude_dirs is None:
            exclude_dirs = ["sensitive"]
        for file_path in sorted(dir_path.rglob(pattern)):
            if any(ex in str(file_path) for ex in exclude_dirs):
                continue
            year_match = re.search(r'(19[4-8]\d)', file_path.name)
            ctx = {}
            if year_match:
                ctx["year"] = int(year_match.group(1))
            result = self.audit_file(file_path, ctx)
            results.append(result)
        return results

    def auto_fix(self, text: str, audit_result: Dict) -> Tuple[str, List[Dict]]:
        fixed = text
        fixes = []
        for hit in sorted(audit_result["hits"], key=lambda x: x["position"], reverse=True):
            replacement = hit.get("replacement", "")
            if not replacement:
                continue
            level = hit.get("level", 0)
            if level == 1:
                word = hit["word"]
                fixed = fixed[:hit["position"]] + replacement + fixed[hit["position"]+len(word):]
                fixes.append({
                    "word": word,
                    "replacement": replacement,
                    "position": hit["position"]
                })
        return fixed, fixes


def print_report(result: Dict, verbose: bool = False):
    print("=" * 60)
    print(f"内容审核报告 - {RESULT_NAMES[result['result']]}")
    if "file_path" in result:
        print(f"文件: {result['file_path']}")
    print(f"字符数: {result['word_count']} | 命中: {result['hit_count']}处")
    print(f"  🔴 一级黑词: {result['level1_count']}处")
    print(f"  🟠 二级红词: {result['level2_count']}处")
    print(f"  🟡 三级黄词: {result['level3_count']}处")
    print("-" * 60)

    if result["hits"]:
        for i, hit in enumerate(result["hits"], 1):
            level_name = LEVEL_NAMES.get(hit["level"], f"{hit.get('event_level', '')}类事件")
            print(f"\n[{i}] {level_name}")
            print(f"    词汇/短语: {hit['word']}")
            print(f"    分类: {hit.get('category', '')}")
            print(f"    上下文: ...{hit['context']}...")
            if hit.get("replacement"):
                print(f"    建议替换: {hit['replacement']}")
            if hit.get("note"):
                print(f"    说明: {hit['note'][:100]}")
    else:
        print("未发现敏感内容。")

    print("=" * 60)


def save_log(results: List[Dict], log_file: Optional[Path] = None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if log_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"audit_{ts}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n审核日志已保存: {log_file}")
    return log_file


def main():
    parser = argparse.ArgumentParser(description="时光调频内容审核脚本")
    parser.add_argument("target", nargs="?", help="要审核的文件/目录路径，或直接提供文本")
    parser.add_argument("--text", "-t", help="直接审核文本内容")
    parser.add_argument("--dir", "-d", help="审核目录下所有md文件")
    parser.add_argument("--year", "-y", type=int, help="指定年代语境（如1958）")
    parser.add_argument("--fix", action="store_true", help="自动修复一级黑词")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细信息")
    parser.add_argument("--no-log", action="store_true", help="不保存日志")
    parser.add_argument("--include-sensitive", action="store_true", help="包含敏感库目录进行扫描（默认排除）")

    args = parser.parse_args()
    auditor = ContentAuditor()

    context = {}
    if args.year:
        context["year"] = args.year

    results = []

    if args.text:
        result = auditor.audit_text(args.text, context)
        print_report(result, args.verbose)
        results.append(result)
        if args.fix:
            fixed, fixes = auditor.auto_fix(args.text, result)
            if fixes:
                print(f"\n自动修复了 {len(fixes)} 处一级黑词:")
                for fix in fixes:
                    print(f"  \"{fix['word']}\" -> \"{fix['replacement']}\"")
                print("\n修复后文本:")
                print(fixed)
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.is_absolute():
            dir_path = PROJECT_ROOT / dir_path
        print(f"正在扫描目录: {dir_path}")
        exclude_dirs = None if args.include_sensitive else ["sensitive"]
        results = auditor.audit_directory(dir_path, exclude_dirs=exclude_dirs)
        passed = sum(1 for r in results if r["result"] == "PASS")
        warned = sum(1 for r in results if r["result"] == "WARN")
        failed = sum(1 for r in results if r["result"] == "FAIL")
        print(f"\n扫描完成: 共{len(results)}个文件 | 通过{passed} | 警告{warned} | 不通过{failed}")
        for r in results:
            if r["result"] != "PASS":
                print_report(r, args.verbose)
    elif args.target:
        target_path = Path(args.target)
        if not target_path.is_absolute():
            target_path = PROJECT_ROOT / target_path
        if target_path.is_file():
            result = auditor.audit_file(target_path, context)
            print_report(result, args.verbose)
            results.append(result)
            if args.fix and result["result"] == "FAIL":
                with open(target_path, "r", encoding="utf-8") as f:
                    text = f.read()
                fixed, fixes = auditor.auto_fix(text, result)
                if fixes:
                    print(f"\n请手动检查并修复上述问题，一级黑词建议替换。")
        elif target_path.is_dir():
            results = auditor.audit_directory(target_path)
            passed = sum(1 for r in results if r["result"] == "PASS")
            warned = sum(1 for r in results if r["result"] == "WARN")
            failed = sum(1 for r in results if r["result"] == "FAIL")
            print(f"\n扫描完成: 共{len(results)}个文件 | 通过{passed} | 警告{warned} | 不通过{failed}")
            for r in results:
                if r["result"] != "PASS":
                    print_report(r, args.verbose)
        else:
            print(f"目标路径不存在: {target_path}")
            sys.exit(1)
    else:
        test_texts = [
            ("今天是1950年10月19日，中国人民志愿军跨过鸭绿江，抗美援朝保家卫国！", 1950, "正常内容"),
            ("那场十年浩劫真是民不聊生，大饥荒饿死了很多人，共匪暴政！", 1965, "包含大量一级黑词"),
            ("1972年，美帝总统尼克松访华，中美关系正常化。", 1972, "美帝在1972年后应禁用"),
            ("那时候大米只要9分钱一斤，后来这首歌成为经典。", 1955, "包含后见之明词汇")
        ]
        print("运行内置测试用例...\n")
        for text, year, desc in test_texts:
            print(f"\n>>> 测试: {desc} (年份{year})")
            print(f"文本: {text[:80]}...")
            ctx = {"year": year}
            result = auditor.audit_text(text, ctx)
            print_report(result, args.verbose)
            results.append(result)

    if results and not args.no_log:
        save_log(results)

    all_pass = all(r["result"] == "PASS" for r in results)
    has_fail = any(r["result"] == "FAIL" for r in results)
    if has_fail:
        sys.exit(1)
    elif not all_pass:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
