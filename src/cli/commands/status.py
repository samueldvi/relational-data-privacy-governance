from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, _: Namespace) -> dict:
    summary = context.status.run()
    print(
        "Project status: "
        f"postgresql={summary['postgresql']}, source_schemas={summary['source_schemas']}, "
        f"source_tables={summary['source_tables']}, source_rows={summary['source_rows']}, "
        f"masked_tables={summary['masked_tables']}, masked_rows={summary['masked_rows']}, "
        f"registry={summary['registry']}({summary['registry_columns']}), "
        f"manifest={summary['manifest']}, last_validation={summary['last_validation']}, "
        f"branch={summary['branch']}, status={summary['status']}."
    )
    return summary
