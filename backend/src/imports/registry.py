from src.imports.adapters import (
    AquatikaAdapter,
    DobroTomskAdapter,
    FiveVerstTrainingAdapter,
    FiveVerstVolunteerAdapter,
    TomskPfdoAdapter,
    TomskPhilharmonicAdapter,
)

VOLUNTEERING_SOURCE_CODES = ("dobro_tomsk", "five_verst_tomsk_volunteer")

adapters = {
    adapter.source_code: adapter
    for adapter in (
        TomskPhilharmonicAdapter(),
        TomskPfdoAdapter(),
        AquatikaAdapter(),
        DobroTomskAdapter(),
        FiveVerstTrainingAdapter(),
        FiveVerstVolunteerAdapter(),
    )
}
