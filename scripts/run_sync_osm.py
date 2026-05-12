import click

from pipeline.jobs.sync_osm import run_sync_osm
from pipeline.utils.config import get_settings
from pipeline.utils.logging import configure_logging


@click.command()
@click.option("--dry-run", is_flag=True, default=False, help="Log changes without writing to DB.")
def main(dry_run: bool) -> None:
    s = get_settings()
    configure_logging(s.log_level)
    run_sync_osm(dry_run=dry_run)


if __name__ == "__main__":
    main()
