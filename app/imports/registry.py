from app.imports.adapters import AquatikaAdapter, CultureRuAdapter, TomskPfdoAdapter

adapters = {adapter.source_code: adapter for adapter in (CultureRuAdapter(), TomskPfdoAdapter(), AquatikaAdapter())}

