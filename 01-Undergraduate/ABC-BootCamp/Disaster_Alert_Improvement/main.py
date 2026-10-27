#!/usr/bin/env python3
"""프로젝트 실행 진입점: python main.py --help"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="재난·실종경보문자 수집 / 댓글 분석 / 시각화")
    commands = parser.add_subparsers(dest="command", required=True)

    crawl = commands.add_parser("crawl", help="재난안전데이터 공유플랫폼 목록 크롤링")
    crawl.add_argument("--output", type=Path, default=ROOT / "data/raw/disaster_messages.csv")
    crawl.add_argument("--start-page", type=int, default=1)
    crawl.add_argument("--max-pages", type=int, default=None, help="생략하면 끝 페이지까지 수집")
    crawl.add_argument("--delay", type=float, default=3.0, help="페이지 로드/스크롤 후 대기 초")
    crawl.add_argument("--headless", action="store_true")
    crawl.add_argument("--no-sandbox", action="store_true", help="필요한 격리 환경에서만 사용")

    analyze = commands.add_parser("analyze", help="YouTube 댓글 CSV 감성·키워드 분석")
    analyze.add_argument("--kind", required=True, choices=["missing", "disaster"], help="실종경보=missing, 재난경보=disaster")
    analyze.add_argument("--comments", type=Path, required=True, help="기존에 수집된 댓글 CSV")
    analyze.add_argument("--lexicon", type=Path, default=ROOT / "data/raw/SentiWord_info.json")
    analyze.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    analyze.add_argument("--font", type=Path, default=None, help="한글 TTF/OTF 폰트. 지정하면 워드클라우드 생성")
    analyze.add_argument("--positive-mask", type=Path, default=None, help="긍정 워드클라우드 마스크 이미지")
    analyze.add_argument("--negative-mask", type=Path, default=None, help="부정 워드클라우드 마스크 이미지")
    analyze.add_argument("--top", type=int, default=20)
    analyze.add_argument("--positive-min", type=float, default=0, help="원본 기준: 0")
    analyze.add_argument("--negative-max", type=float, default=-20, help="원본 기준: -20")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    try:
        if args.command == "crawl":
            from disaster_alert_improvement.disaster_crawler import crawl_disaster_alerts

            crawl_disaster_alerts(
                args.output,
                start_page=args.start_page,
                max_pages=args.max_pages,
                delay=args.delay,
                headless=args.headless,
                no_sandbox=args.no_sandbox,
            )
        elif args.command == "analyze":
            from disaster_alert_improvement.pipeline import analyze_comments

            summary = analyze_comments(
                kind=args.kind,
                comments_csv=args.comments,
                lexicon_json=args.lexicon,
                output_dir=args.output_dir,
                font_path=args.font,
                positive_mask=args.positive_mask,
                negative_mask=args.negative_mask,
                top_n=args.top,
                positive_min=args.positive_min,
                negative_max=args.negative_max,
            )
            print(f"[{args.kind}] 분석 완료: {summary} / 저장 경로: {args.output_dir / args.kind}")
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
