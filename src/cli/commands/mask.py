from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, args: Namespace) -> dict:
    result = context.masking.run(dry_run=args.dry_run, validate_only=args.validate_only)
    if args.dry_run:
        print(
            f"Mask dry-run valid: tables={result['tables']}, batches={result['batch_sets']}, "
            f"strategy={result['ambiguous_strategy']}, writes=0."
        )
    elif args.validate_only:
        print(
            f"Masked state valid: tables={result['tables']}, rows={result['rows']}, "
            f"validations={result['validations']}."
        )
    else:
        print(
            f"Masking completed: tables={result['tables_processed']}, "
            f"rows={sum(result['masked_rows_by_table'].values())}, "
            f"validations={len(result['validations'])}, checksum={result['global_checksum']}."
        )
    return result
