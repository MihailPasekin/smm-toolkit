from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class UserOptions:
    source: str
    mode: str
    quality: str
    segment_duration: int | None


def prompt_for_options(
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> UserOptions:
    """Collect the options needed for an interactive CLI run."""

    source = input_func("Вставь ссылку на видео или путь к файлу: ").strip()
    while not source:
        output_func("Ссылка или путь не могут быть пустыми.")
        source = input_func("Вставь ссылку на видео или путь к файлу: ").strip()

    mode = _choose(
        input_func,
        output_func,
        "Что скачать?",
        {
            "1": ("Видео", "video"),
            "2": ("Видео с субтитрами", "subtitled"),
            "3": ("Только аудио (MP3)", "audio"),
        },
    )

    if mode == "audio":
        return UserOptions(source, mode, "best", None)

    quality = _choose(
        input_func,
        output_func,
        "Какое качество видео нужно?",
        {
            "1": ("Лучшее доступное", "best"),
            "2": ("1080p или ниже", "1080"),
            "3": ("720p или ниже", "720"),
            "4": ("480p или ниже", "480"),
            "5": ("360p или ниже", "360"),
        },
    )
    split = _choose(
        input_func,
        output_func,
        "Резать видео на клипы по 60 секунд?",
        {"1": ("Да", True), "2": ("Нет", False)},
    )

    return UserOptions(source, mode, quality, 60 if split else None)


def _choose(
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
    question: str,
    choices: dict[str, tuple[str, object]],
):
    output_func(question)
    for key, (label, _value) in choices.items():
        output_func(f"  {key}. {label}")

    while True:
        answer = input_func("Выбери номер: ").strip()
        if answer in choices:
            return choices[answer][1]
        output_func("Нужен номер одного из вариантов.")
