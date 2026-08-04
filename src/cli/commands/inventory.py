from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, _: Namespace) -> dict:
    summary = context.inventory.run()
    print(
        "Inventory generated: "
        f"schemas={summary['schemas']}, tables={summary['tables']}, columns={summary['columns']}, "
        f"PK={summary['primary_keys']}, FK={summary['foreign_keys']}, "
        f"UNIQUE={summary['unique_constraints']}, CHECK={summary['check_constraints']}."
    )
    return summary
