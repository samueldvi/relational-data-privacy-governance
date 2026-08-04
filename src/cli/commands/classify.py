from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, _: Namespace) -> dict:
    summary = context.classification.run()
    print(
        f"Classification generated: columns={summary['columns']}; categories="
        + ",".join(f"{key}:{value}" for key, value in summary["categories"].items())
        + "; review="
        + ",".join(f"{key}:{value}" for key, value in summary["statuses"].items())
        + "."
    )
    return summary
