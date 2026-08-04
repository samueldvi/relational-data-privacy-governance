from argparse import Namespace

from src.application.context import ApplicationContext
from src.application.pipeline import EndToEndPipeline


def execute(context: ApplicationContext, pipeline: EndToEndPipeline, args: Namespace) -> dict:
    result = pipeline.run(seed=args.seed, check_idempotence=args.check_idempotence)
    print("End-to-end summary:")
    for phase in result.phases:
        print(f"- {phase.name}: success ({phase.duration_seconds:.3f}s)")
    print(
        f"- result: rows={result.rows}, classified_columns={result.classified_columns}, "
        f"masked_tables={result.masked_tables}, validations={result.validations}, "
        f"checksum={result.checksum}."
    )
    return {"result": result}
