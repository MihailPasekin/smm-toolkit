# scripts/toolkit.py
from __future__ import annotations

import argparse
import sys
import subprocess

from config import VERSION, QUALITY_CHOICES
from errors import PipelineError
from pipeline import run_pipeline
from interactive import prompt_for_options


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SMM Toolkit V1.5 — URL/local video → clips + subtitles")
    parser.add_argument("source", nargs="?", help="URL или путь к локальному видео")
    parser.add_argument("--segment-duration", "--duration", dest="segment_duration", type=int, default=60)
    parser.add_argument("--subtitles", choices=("auto", "yes", "no"), default="auto")
    parser.add_argument("--mode", choices=("video", "subtitled", "audio"))
    parser.add_argument("--quality", choices=QUALITY_CHOICES, default="best")
    parser.add_argument("--no-split", action="store_true")
    parser.add_argument("--output", default="output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.source is None:
            options = prompt_for_options()
            source = options.source
            segment_duration = options.segment_duration
            output_mode = options.mode
            quality = options.quality
        else:
            source = args.source
            segment_duration = None if args.no_split else args.segment_duration
            output_mode = args.mode
            quality = args.quality

        run_pipeline(
            source,
            segment_duration=segment_duration,
            subtitles=args.subtitles,
            output_root=args.output,
            quality=quality,
            output_mode=output_mode,
        )
        return 0
    except PipelineError as exc:
        print(f"❌ Ошибка: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем.", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as exc:
        print(f"❌ Внешняя команда завершилась с кодом {exc.returncode}.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())