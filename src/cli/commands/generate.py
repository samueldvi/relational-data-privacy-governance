from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, args: Namespace) -> dict:
    summary = context.generation.run(args.seed)
    print(
        f"Synthetic dataset generated: seed={summary['seed']}, "
        f"tables={summary['tables']}, rows={summary['rows']}."
    )
    return summary
