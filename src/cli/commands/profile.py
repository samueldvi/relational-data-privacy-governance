from argparse import Namespace

from src.application.context import ApplicationContext


def execute(context: ApplicationContext, _: Namespace) -> dict:
    metadata = context.profiling.run()
    print(
        f"Profiling generated: columns={metadata['column_count']}, "
        f"pattern_evidence={metadata['pattern_evidence_column_count']}, "
        f"privacy_patterns={metadata['suspicious_column_count']}, "
        f"redacted_samples={metadata['redacted_sample_count']}."
    )
    return metadata
