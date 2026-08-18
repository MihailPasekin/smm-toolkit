# SMM Toolkit — V1.5

Единый pipeline для обработки видео:

- URL или локальный файл как вход;
- скачивание URL непосредственно внутри `toolkit.py`;
- автоматическое определение длительности;
- короткие видео не режутся;
- длинные видео режутся на клипы;
- VAD-проверка речи перед Whisper;
- `--subtitles auto|yes|no`;
- локальные timestamps субтитров для каждого клипа;
- структурированный `output/<video>/`;
- `metadata.json`;
- тесты;
- архитектурная точка расширения под Smart Cut.

## Требования

Нужны системные программы:

```bash
brew install ffmpeg
```

Python-зависимости:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Запуск

Локальный файл:

```bash
python scripts/toolkit.py /path/to/video.mp4
```

URL:

```bash
python scripts/toolkit.py "https://..."
```

Режим субтитров:

```bash
python scripts/toolkit.py video.mp4 --subtitles auto
python scripts/toolkit.py video.mp4 --subtitles yes
python scripts/toolkit.py video.mp4 --subtitles no
```

Длина клипа:

```bash
python scripts/toolkit.py video.mp4 --segment-duration 60
```

## Output

```text
output/
└── video_name/
    ├── source/
    │   └── original.mp4
    ├── clips/
    │   ├── clip_001.mp4
    │   └── clip_002_subtitled.mp4
    ├── subtitles/
    │   ├── source.srt
    │   ├── clip_001.srt
    │   └── clip_002.srt
    └── metadata.json
```

`download.py`, `split.py` и `burn_subs.py` больше не являются частью pipeline. Их ответственность перенесена в единый orchestrator и внутренние модули.

## Smart Cut

`CutStrategy` задаёт контракт:

```python
plan(duration, max_duration) -> list[Cut]
```

Сейчас используется `FixedDurationCutStrategy`. В будущем Smart Cut сможет заменить только стратегию нарезки, не переписывая скачивание, VAD, Whisper, субтитры, rendering и metadata.

## Тесты

```bash
pytest -q
```


## V1.5 subtitle behavior

`--subtitles auto` uses VAD as a cheap gate before Whisper. If VAD passes but
Whisper returns zero text segments, this is treated as a normal "no usable
speech" outcome: no empty SRT files are created and the video is preserved
without burned subtitles.

`--subtitles yes` is strict: if Whisper cannot produce any text segments, the
pipeline exits with a clear error instead of sending an empty SRT to FFmpeg.

`--subtitles no` skips both VAD and Whisper.
