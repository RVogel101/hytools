#!/usr/bin/env python3
"""Run the full extraction pipeline end-to-end.

This script orchestrates execution of all extraction tools in the correct order,
with error handling and progress tracking. Can be used locally or in CI/CD.

Usage:
  python run_extraction_pipeline.py --project lousardzag
  python run_extraction_pipeline.py --project lousardzag --dry-run
  python run_extraction_pipeline.py --project lousardzag --skip validate_contract_alignment
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    tool_name: str
    tool_index: int
    total_tools: int
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    skipped: bool = False
    
    @property
    def success(self) -> bool:
        return self.returncode == 0
    
    @property
    def status_icon(self) -> str:
        if self.skipped:
            return "⊘"
        elif self.success:
            return "✓"
        else:
            return "✗"


class ExtractionPipelineRunner:
    """Orchestrates execution of the full extraction pipeline."""
    
    def __init__(self, project_root: Path, dry_run: bool = False, skip_tools: list[str] | None = None):
        self.project_root = project_root
        self.dry_run = dry_run
        self.skip_tools = set(skip_tools or [])
        self.results: list[PipelineResult] = []
        self.extraction_dir = Path(__file__).resolve().parent
    
    def run_pipeline(self, tools: list[str]) -> bool:
        """Execute the full pipeline."""
        print("=" * 80)
        print("EXTRACTION PIPELINE EXECUTION")
        print("=" * 80)
        print(f"Project root: {self.project_root}")
        print(f"Extraction tools dir: {self.extraction_dir}")
        print(f"Total tools: {len(tools)}")
        print(f"Skip tools: {self.skip_tools if self.skip_tools else 'none'}")
        print(f"Dry run: {self.dry_run}")
        print("=" * 80)
        
        for idx, tool_name in enumerate(tools, 1):
            if tool_name in self.skip_tools:
                print(f"\n[{idx}/{len(tools)}] ⊘ Skipping {tool_name}")
                self.results.append(PipelineResult(
                    tool_name=tool_name,
                    tool_index=idx,
                    total_tools=len(tools),
                    returncode=0,
                    stdout="",
                    stderr="",
                    duration_seconds=0,
                    skipped=True,
                ))
                continue
            
            result = self._run_tool(tool_name, idx, len(tools))
            self.results.append(result)
            
            print(f"{result.status_icon} [{idx}/{len(tools)}] {tool_name} (exit: {result.returncode}, {result.duration_seconds:.2f}s)")
            
            if not result.success and result.returncode != 0:
                print(f"     ✗ Failed with exit code {result.returncode}")
                # Don't stop - continue with other tools
        
        print("\n" + "=" * 80)
        print("PIPELINE SUMMARY")
        print("=" * 80)
        self._print_summary()
        print("=" * 80)
        
        # Check if all non-skipped tools succeeded
        failed = [r for r in self.results if not r.skipped and not r.success]
        if failed:
            print(f"\n❌ Pipeline failed: {len(failed)} tool(s) failed")
            for r in failed:
                print(f"   - {r.tool_name}")
            return False
        else:
            print(f"\n✅ Pipeline completed successfully")
            return True
    
    def _run_tool(self, tool_name: str, idx: int, total: int) -> PipelineResult:
        """Execute a single extraction tool."""
        import time
        
        tool_script = self.extraction_dir / f"{tool_name}.py"
        if not tool_script.exists():
            return PipelineResult(
                tool_name=tool_name,
                tool_index=idx,
                total_tools=total,
                returncode=1,
                stdout="",
                stderr=f"Tool script not found: {tool_script}",
                duration_seconds=0,
            )
        
        cmd = [sys.executable, str(tool_script)]
        
        print(f"\n[{idx}/{total}] Running {tool_name}...")
        
        if self.dry_run:
            print(f"     [DRY RUN] Would execute: {' '.join(cmd)}")
            return PipelineResult(
                tool_name=tool_name,
                tool_index=idx,
                total_tools=total,
                returncode=0,
                stdout="[DRY RUN]",
                stderr="",
                duration_seconds=0,
            )
        
        try:
            start = time.time()
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per tool
            )
            duration = time.time() - start
            
            return PipelineResult(
                tool_name=tool_name,
                tool_index=idx,
                total_tools=total,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            return PipelineResult(
                tool_name=tool_name,
                tool_index=idx,
                total_tools=total,
                returncode=124,
                stdout="",
                stderr="Tool execution timed out (>300 seconds)",
                duration_seconds=300,
            )
        except Exception as e:
            return PipelineResult(
                tool_name=tool_name,
                tool_index=idx,
                total_tools=total,
                returncode=1,
                stdout="",
                stderr=f"Error executing tool: {e}",
                duration_seconds=0,
            )
    
    def _print_summary(self) -> None:
        """Print execution summary."""
        total = len(self.results)
        succeeded = len([r for r in self.results if r.success or r.skipped])
        skipped = len([r for r in self.results if r.skipped])
        failed = total - succeeded
        total_time = sum(r.duration_seconds for r in self.results)
        
        print(f"Total tools: {total}")
        print(f"Succeeded: {succeeded - skipped}")
        print(f"Skipped: {skipped}")
        print(f"Failed: {failed}")
        print(f"Total execution time: {total_time:.2f}s")
        print()
        
        for result in self.results:
            status = result.status_icon
            if result.skipped:
                print(f"{status} {result.tool_name}: (skipped)")
            else:
                print(f"{status} {result.tool_name}: exit {result.returncode} ({result.duration_seconds:.2f}s)")
                if result.stdout:
                    for line in result.stdout.split('\n')[:3]:
                        if line.strip():
                            print(f"   {line[:70]}")
                if result.stderr:
                    for line in result.stderr.split('\n')[:2]:
                        if line.strip():
                            print(f"   ERROR: {line[:70]}")
    
    def export_results(self, output_path: Path) -> None:
        """Export execution results as JSON."""
        results_data = {
            "execution": {
                "total_tools": len(self.results),
                "succeeded": len([r for r in self.results if r.success or r.skipped]),
                "skipped": len([r for r in self.results if r.skipped]),
                "failed": len([r for r in self.results if not r.success and not r.skipped]),
                "total_duration_seconds": sum(r.duration_seconds for r in self.results),
                "dry_run": self.dry_run,
            },
            "tools": [
                {
                    "name": r.tool_name,
                    "index": r.tool_index,
                    "returncode": r.returncode,
                    "duration_seconds": r.duration_seconds,
                    "skipped": r.skipped,
                    "success": r.success,
                    "stdout_lines": len(r.stdout.split('\n')),
                    "stderr_lines": len(r.stderr.split('\n')),
                }
                for r in self.results
            ]
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Results exported to: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full extraction pipeline end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline from lousardzag project
  python run_extraction_pipeline.py --project lousardzag
  
  # Dry run (show what would execute)
  python run_extraction_pipeline.py --project lousardzag --dry-run
  
  # Skip specific tools
  python run_extraction_pipeline.py --project lousardzag \\
    --skip validate_contract_alignment \\
    --skip ingest_wa_fingerprints_to_contracts
        """,
    )
    parser.add_argument(
        "--project", 
        required=True,
        help="Project name (lousardzag) or root path"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would execute without running"
    )
    parser.add_argument(
        "--skip",
        action="append",
        dest="skip_tools",
        help="Skip specific tools (can be used multiple times)"
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("08-data/pipeline_execution_report.json"),
        help="JSON file to export execution results"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    
    # Resolve project root
    if args.project == "lousardzag":
        project_root = Path.cwd()  # Assume running from lousardzag root
    else:
        project_root = Path(args.project).resolve()
    
    if not project_root.exists():
        print(f"Error: Project root not found: {project_root}")
        return 1
    
    # Tools in recommended execution order
    tools = [
        "export_core_contracts_jsonl",
        "validate_contract_alignment",
        "ingest_wa_fingerprints_to_contracts",
        "merge_document_records",
        "merge_document_records_with_profiles",
        "extract_fingerprint_index",
        "materialize_dialect_views",
        "summarize_unified_documents",
    ]
    
    runner = ExtractionPipelineRunner(
        project_root=project_root,
        dry_run=args.dry_run,
        skip_tools=args.skip_tools,
    )
    
    success = runner.run_pipeline(tools)
    runner.export_results(project_root / args.output_json)
    
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
