from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.classifiers.enums import AgePreset
from src.exceptions import AppError

PRESETS: dict[AgePreset, tuple[int, int | None, str]] = {
    AgePreset.TEENS_12_17: (12, 17, "Подростки"),
    AgePreset.YOUTH_18_24: (18, 24, "Молодёжь"),
    AgePreset.ADULTS_25_39: (25, 39, "Молодые взрослые"),
    AgePreset.ADULTS_40_59: (40, 59, "Взрослые"),
    AgePreset.SENIORS_60_PLUS: (60, None, "Старшее поколение"),
    AgePreset.ALL_ADULTS_18_PLUS: (18, None, "Все совершеннолетние"),
}


def today_tomsk() -> date:
    return datetime.now(ZoneInfo("Asia/Tomsk")).date()


def calculate_age(birth_date: date, on_date: date) -> int:
    return (
        on_date.year
        - birth_date.year
        - ((on_date.month, on_date.day) < (birth_date.month, birth_date.day))
    )


def is_age_eligible(age: int, min_age: int, max_age: int | None) -> bool:
    return age >= min_age and (max_age is None or age <= max_age)


def validate_age_range(min_age: int, max_age: int | None) -> None:
    if (
        min_age < 0
        or (max_age is not None and max_age < min_age)
        or (min_age < 18 <= (max_age or min_age))
    ):
        raise AppError("INVALID_AGE_RANGE", "Некорректный возрастной диапазон")


def build_age_label(min_age: int, max_age: int | None, preset: AgePreset | None = None) -> str:
    prefix = PRESETS.get(preset, (0, None, "Участники"))[2] if preset else "Участники"
    return f"{prefix} {min_age}+" if max_age is None else f"{prefix} {min_age}–{max_age}"


def resolve_age_range(
    preset: AgePreset, min_age: int | None, max_age: int | None
) -> tuple[int, int | None]:
    if preset != AgePreset.CUSTOM:
        return PRESETS[preset][:2]
    if min_age is None:
        raise AppError("INVALID_AGE_RANGE", "Для CUSTOM требуется min_age")
    validate_age_range(min_age, max_age)
    return min_age, max_age
