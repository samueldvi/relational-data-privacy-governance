from __future__ import annotations

from argparse import Namespace

from src.application.context import ApplicationContext
from src.domain.schema_drift import DriftKind
from src.shared.errors import SchemaDriftError


def execute(context: ApplicationContext, args: Namespace) -> dict[str, int | bool]:
    if args.write_baseline:
        baseline_summary = context.drift.write_baseline()
        print(
            "Schema baseline written explicitly: "
            f"schemas={baseline_summary['schemas']}, tables={baseline_summary['tables']}, "
            f"columns={baseline_summary['columns']}, constraints={baseline_summary['constraints']}, "
            f"logical_relationships={baseline_summary['logical_relationships']}."
        )
        return baseline_summary

    report = context.drift.report()
    report_summary: dict[str, int | bool] = {
        "drift": report.has_drift,
        "breaking": report.count(DriftKind.BREAKING),
        "non_breaking": report.count(DriftKind.NON_BREAKING),
        "governance": report.count(DriftKind.GOVERNANCE),
    }
    print(
        "Schema drift report: "
        f"status={'drift-detected' if report.has_drift else 'clean'}, "
        f"breaking={report_summary['breaking']}, non_breaking={report_summary['non_breaking']}, "
        f"governance={report_summary['governance']}."
    )
    for item in report.items:
        print(
            f"- [{item.severity.value}] {item.kind.value} {item.path}: {item.message} Remediation: {item.remediation}"
        )
    if args.check and report.has_drift:
        raise SchemaDriftError(f"Schema drift check failed with {len(report.items)} finding(s).")
    return report_summary
