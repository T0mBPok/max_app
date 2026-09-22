import asyncio

import typer

from src.database import SessionLocal
from src.exceptions import AppError
from src.imports.logic import run_import
from src.imports.registry import adapters

app = typer.Typer(help="Запуск импортов активностей")


async def execute(codes: list[str]) -> None:
    failed = False
    async with SessionLocal() as session:
        for code in codes:
            adapter = adapters.get(code)
            if not adapter:
                raise typer.BadParameter(f"Неизвестный источник: {code}")
            try:
                result = await run_import(session, adapter)
                typer.echo(
                    f"{code}: {result.status.value}, created={result.created_count}, "
                    f"updated={result.updated_count}"
                )
            except AppError as exc:
                failed = True
                typer.echo(f"{code}: FAILED ({exc.code}: {exc.message})", err=True)
    if failed:
        raise typer.Exit(1)


@app.command("run")
def run(source_code: str):
    asyncio.run(execute([source_code]))


@app.command("run-all")
def run_all():
    asyncio.run(execute(list(adapters)))


if __name__ == "__main__":
    app()
