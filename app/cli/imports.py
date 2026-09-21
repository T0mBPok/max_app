import asyncio

import typer

from app.db import SessionLocal
from app.imports.registry import adapters
from app.imports.service import run_import

app = typer.Typer(help="Запуск импортов активностей")


async def execute(codes: list[str]) -> None:
    async with SessionLocal() as session:
        for code in codes:
            adapter = adapters.get(code)
            if not adapter: raise typer.BadParameter(f"Неизвестный источник: {code}")
            result = await run_import(session, adapter)
            typer.echo(f"{code}: {result.status.value}, created={result.created_count}, updated={result.updated_count}")


@app.command("run")
def run(source_code: str): asyncio.run(execute([source_code]))


@app.command("run-all")
def run_all(): asyncio.run(execute(list(adapters)))


if __name__ == "__main__": app()

