from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, args: Namespace) -> dict:
    summary = context.validation.run(check_idempotence=args.check_idempotence)
    suffix = ", idempotence=verified" if summary["idempotent"] else ""
    print(
        f"Validation successful: tables={summary['tables']}, rows={summary['rows']}, "
        f"checks={summary['validations']}, checksum={summary['checksum']}{suffix}."
    )
    return summary
