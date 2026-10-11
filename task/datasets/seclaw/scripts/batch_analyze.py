#!/usr/bin/env python3
"""
ARCA Batch Evaluation Analysis Script

Reads jobs.jsonl from batch evaluation output and produces per-task and per-model analysis.

Usage:
    python scripts/batch_analyze.py \
        --batch-logs batch_logs \
        --batch-name batch_eval_20260511_abcd \
        [--low-threshold 0.3] [--high-threshold 0.8] [--diff-threshold 0.3] \
        [--output-dir <path>]

Output:
    report.md     - Human-readable Markdown report
    analysis.json - Structured JSON with all computed metrics
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_jobs(jobs_file: str) -> list[dict]:
    """Load job records from jobs.jsonl."""
    jobs = []
    with open(jobs_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))
    return jobs


def categorize_task(scores: dict[str, float], low_threshold: float,
                    high_threshold: float, diff_threshold: float) -> tuple[str, dict]:
    """Categorize a task based on model scores.

    Returns:
        (category, stats) where stats contains mean, min, max, range, score dict
    """
    if not scores:
        return "no_data", {"mean": None, "min": None, "max": None, "range": None, "scores": {}}

    values = list(scores.values())
    mean_score = sum(values) / len(values)
    min_score = min(values)
    max_score = max(values)
    score_range = max_score - min_score

    stats = {
        "mean": round(mean_score, 4),
        "min": round(min_score, 4),
        "max": round(max_score, 4),
        "range": round(score_range, 4),
        "scores": {k: round(v, 4) for k, v in scores.items()},
    }

    # Priority: easy > hard > discriminative > uncertain (aligned with review methodology)
    if min_score >= high_threshold:
        category = "easy"
    elif max_score < low_threshold:
        category = "hard"
    elif score_range >= diff_threshold:
        category = "discriminative"
    else:
        category = "uncertain"

    return category, stats


def compute_per_model(task_data: dict[str, tuple[str, dict]],
                      differentiated_tasks: set[str]) -> dict[str, dict]:
    """Compute per-model aggregate statistics."""
    model_scores = defaultdict(list)
    model_diff_scores = defaultdict(list)
    model_wins = defaultdict(int)
    model_ties = defaultdict(int)

    for task_name, (category, stats) in task_data.items():
        scores = stats.get("scores", {})
        if not scores:
            continue

        max_score = max(scores.values())
        winners = [m for m, s in scores.items() if s == max_score]

        for model, score in scores.items():
            model_scores[model].append(score)
            if task_name in differentiated_tasks:
                model_diff_scores[model].append(score)
            if len(winners) == 1 and model in winners:
                model_wins[model] += 1
            elif len(winners) > 1 and model in winners:
                model_ties[model] += 1

    result = {}
    for model in sorted(model_scores.keys()):
        all_scores = model_scores[model]
        diff_scores = model_diff_scores.get(model, [])

        # Win rate: solo wins + 0.5 * ties
        total_tasks = len(all_scores)
        solo_wins = model_wins[model]
        ties = model_ties[model]
        win_rate = (solo_wins + 0.5 * ties) / total_tasks if total_tasks > 0 else 0.0

        result[model] = {
            "avg_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else None,
            "avg_score_differentiated": round(sum(diff_scores) / len(diff_scores), 4) if diff_scores else None,
            "win_rate": round(win_rate, 4),
            "solo_wins": solo_wins,
            "ties": ties,
            "task_count": total_tasks,
            "differentiated_task_count": len(diff_scores),
        }

    return result


def generate_report(task_data: dict[str, tuple[str, dict]],
                    per_model: dict[str, dict],
                    template_map: dict[str, str],
                    thresholds: dict[str, float],
                    batch_name: str,
                    total_jobs: int,
                    completed_evals: int,
                    failed_evals: int,
                    skipped_downloads: int,
                    failed_downloads: int) -> str:
    """Generate Markdown report."""
    lines = []

    lines.append("# Batch Evaluation Report")
    lines.append("")
    lines.append(f"**Batch**: {batch_name}")
    lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Thresholds**: hard < {thresholds['low']} (all scores), easy >= {thresholds['high']} (all scores), discriminative range >= {thresholds['diff']}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total jobs | {total_jobs} |")
    lines.append(f"| Completed evaluations | {completed_evals} |")
    lines.append(f"| Failed evaluations | {failed_evals} |")
    lines.append(f"| Skipped (download failed) | {skipped_downloads} |")
    lines.append(f"| Failed downloads | {failed_downloads} |")

    model_count = len(per_model)
    lines.append(f"| Model count | {model_count} |")

    # Category counts
    categories = defaultdict(list)
    for task_name, (category, stats) in task_data.items():
        categories[category].append(task_name)

    lines.append(f"| Easy tasks | {len(categories.get('easy', []))} |")
    lines.append(f"| Hard tasks | {len(categories.get('hard', []))} |")
    lines.append(f"| Discriminative tasks | {len(categories.get('discriminative', []))} |")
    lines.append(f"| Uncertain tasks | {len(categories.get('uncertain', []))} |")
    lines.append("")

    # Template mapping
    if template_map:
        lines.append("## Template Mapping")
        lines.append("")
        lines.append("| Template ID | Model Name |")
        lines.append("|-------------|------------|")
        for tid, mname in sorted(template_map.items()):
            lines.append(f"| {tid} | {mname} |")
        lines.append("")

    # Per-model results
    lines.append("## Per-Model Results")
    lines.append("")
    lines.append("| Model | Avg Score | Avg (Diff. Tasks) | Win Rate | Task Count |")
    lines.append("|-------|-----------|-------------------|----------|------------|")
    for model in sorted(per_model.keys()):
        m = per_model[model]
        avg = f"{m['avg_score']:.4f}" if m['avg_score'] is not None else "N/A"
        avg_diff = f"{m['avg_score_differentiated']:.4f}" if m['avg_score_differentiated'] is not None else "N/A"
        win = f"{m['win_rate']:.1%}"
        lines.append(f"| {model} | {avg} | {avg_diff} | {win} | {m['task_count']} |")
    lines.append("")

    # Per-task categories
    model_names = sorted(per_model.keys())

    for cat_name, cat_title, cat_desc in [
        ("easy", "Easy Tasks", f"all scores >= {thresholds['high']}"),
        ("hard", "Hard Tasks", f"all scores < {thresholds['low']}"),
        ("discriminative", "Discriminative Tasks", f"range >= {thresholds['diff']}"),
        ("uncertain", "Uncertain Tasks", "other"),
    ]:
        tasks_in_cat = categories.get(cat_name, [])
        lines.append(f"### {cat_title} ({len(tasks_in_cat)} tasks, {cat_desc})")
        lines.append("")

        if not tasks_in_cat:
            lines.append("_No tasks in this category._")
            lines.append("")
            continue

        # Header
        header = "| Task | " + " | ".join(model_names) + " | Mean | Range |"
        separator = "|------|" + "|".join(["-------"] * len(model_names)) + "|------|-------|"
        lines.append(header)
        lines.append(separator)

        # Sort by mean score
        sorted_tasks = sorted(tasks_in_cat, key=lambda t: task_data[t][1].get("mean", 0) or 0)

        for task_name in sorted_tasks:
            _, stats = task_data[task_name]
            scores = stats.get("scores", {})
            row = f"| {task_name} |"
            for model in model_names:
                score = scores.get(model, None)
                row += f" {score if score is not None else 'N/A'} |"
            row += f" {stats.get('mean', 'N/A')} | {stats.get('range', 'N/A')} |"
            lines.append(row)
        lines.append("")

    # Failed evaluations
    lines.append("## Failed Evaluations")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze batch evaluation results")
    parser.add_argument("--batch-logs", required=True, help="Batch logs directory")
    parser.add_argument("--batch-name", required=True, help="Batch name")
    parser.add_argument("--low-threshold", type=float, default=None,
                        help="Hard threshold: all scores < this value (default: from BATCH_EVAL_LOW_SCORE_THRESHOLD or 0.3)")
    parser.add_argument("--high-threshold", type=float, default=None,
                        help="Easy threshold: all scores >= this value (default: from BATCH_EVAL_HIGH_SCORE_THRESHOLD or 0.8)")
    parser.add_argument("--diff-threshold", type=float, default=None,
                        help="Discriminative threshold: score range >= this value (default: from BATCH_EVAL_DIFF_THRESHOLD or 0.3)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for reports (default: {batch_logs}/{batch_name})")
    args = parser.parse_args()

    # Resolve thresholds: CLI arg > env var > default
    low_threshold = args.low_threshold if args.low_threshold is not None else float(
        os.getenv("BATCH_EVAL_LOW_SCORE_THRESHOLD", "0.3"))
    high_threshold = args.high_threshold if args.high_threshold is not None else float(
        os.getenv("BATCH_EVAL_HIGH_SCORE_THRESHOLD", "0.8"))
    diff_threshold = args.diff_threshold if args.diff_threshold is not None else float(
        os.getenv("BATCH_EVAL_DIFF_THRESHOLD", "0.3"))

    # Load .env for thresholds
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        # Re-resolve thresholds from env after loading .env
        if args.low_threshold is None:
            low_threshold = float(os.getenv("BATCH_EVAL_LOW_SCORE_THRESHOLD", str(low_threshold)))
        if args.high_threshold is None:
            high_threshold = float(os.getenv("BATCH_EVAL_HIGH_SCORE_THRESHOLD", str(high_threshold)))
        if args.diff_threshold is None:
            diff_threshold = float(os.getenv("BATCH_EVAL_DIFF_THRESHOLD", str(diff_threshold)))

    # Load jobs
    batch_dir = Path(args.batch_logs) / args.batch_name
    jobs_file = batch_dir / "jobs.jsonl"

    if not jobs_file.exists():
        print(f"Error: jobs.jsonl not found at {jobs_file}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Loading jobs from {jobs_file}")
    jobs = load_jobs(str(jobs_file))

    # Output directory
    output_dir = Path(args.output_dir) if args.output_dir else batch_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Count statuses
    total_jobs = len(jobs)
    completed_evals = sum(1 for j in jobs if j.get("eval_status") == "completed")
    failed_evals = sum(1 for j in jobs if j.get("eval_status") == "failed")
    skipped_downloads = sum(1 for j in jobs if j.get("download_status") != "completed")
    failed_downloads = sum(1 for j in jobs if j.get("download_status") == "failed")

    print(f"[INFO] Total jobs: {total_jobs}, Completed: {completed_evals}, "
          f"Failed evals: {failed_evals}, Failed downloads: {failed_downloads}")

    # Build per-task scores: task_name -> {model_name -> score}
    task_model_scores = defaultdict(dict)
    template_map = {}
    failed_eval_list = []

    for job in jobs:
        template_id = job.get("template_id", "")
        model_name = job.get("model_name", template_id)

        # Build template map
        if template_id and model_name:
            template_map[template_id] = model_name

        if job.get("eval_status") == "completed":
            task_name = job.get("task_name", "")
            score = job.get("total_score")
            if score is not None and task_name:
                task_model_scores[task_name][model_name] = score
        elif job.get("eval_status") == "failed":
            failed_eval_list.append({
                "task_name": job.get("task_name", ""),
                "model_name": model_name,
                "error": job.get("error", ""),
            })

    # Per-task analysis
    print(f"[INFO] Analyzing {len(task_model_scores)} tasks across {len(template_map)} models")
    print(f"[INFO] Thresholds: hard < {low_threshold} (all scores), easy >= {high_threshold} (all scores), discriminative range >= {diff_threshold}")

    task_data = {}
    for task_name, scores in task_model_scores.items():
        category, stats = categorize_task(scores, low_threshold, high_threshold, diff_threshold)
        task_data[task_name] = (category, stats)

    # Identify differentiated tasks
    differentiated_tasks = {t for t, (c, _) in task_data.items() if c == "discriminative"}

    # Per-model analysis
    per_model = compute_per_model(task_data, differentiated_tasks)

    # Category counts
    category_counts = defaultdict(int)
    for _, (category, _) in task_data.items():
        category_counts[category] += 1

    print(f"[INFO] Categories: easy={category_counts.get('easy', 0)}, "
          f"hard={category_counts.get('hard', 0)}, "
          f"discriminative={category_counts.get('discriminative', 0)}, "
          f"uncertain={category_counts.get('uncertain', 0)}")

    # Generate report
    report = generate_report(
        task_data=task_data,
        per_model=per_model,
        template_map=template_map,
        thresholds={"low": low_threshold, "high": high_threshold, "diff": diff_threshold},
        batch_name=args.batch_name,
        total_jobs=total_jobs,
        completed_evals=completed_evals,
        failed_evals=failed_evals,
        skipped_downloads=skipped_downloads,
        failed_downloads=failed_downloads,
    )

    # Add failed evaluations to report
    if failed_eval_list:
        report += "| Task | Model | Error |\n"
        report += "|------|-------|-------|\n"
        for fe in failed_eval_list:
            report += f"| {fe['task_name']} | {fe['model_name']} | {fe['error']} |\n"
        report += "\n"
    else:
        report += "No failed evaluations.\n\n"

    # Write report
    report_path = output_dir / "report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"[INFO] Report written to {report_path}")

    # Build analysis JSON
    per_task_result = {}
    for task_name, (category, stats) in sorted(task_data.items()):
        per_task_result[task_name] = {
            "category": category,
            "mean_score": stats["mean"],
            "min_score": stats["min"],
            "max_score": stats["max"],
            "score_range": stats["range"],
            "scores": stats["scores"],
        }

    analysis = {
        "batch_name": args.batch_name,
        "timestamp": datetime.now().isoformat(),
        "thresholds": {
            "hard": low_threshold,
            "easy": high_threshold,
            "discriminative": diff_threshold,
        },
        "summary": {
            "total_jobs": total_jobs,
            "completed_evals": completed_evals,
            "failed_evals": failed_evals,
            "failed_downloads": failed_downloads,
            "model_count": len(template_map),
            "task_count": len(task_data),
            "category_counts": dict(category_counts),
        },
        "template_map": template_map,
        "per_model": per_model,
        "per_task": per_task_result,
        "failed_evals": failed_eval_list,
    }

    # Write analysis JSON
    analysis_path = output_dir / "analysis.json"
    with open(analysis_path, "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"[INFO] Analysis written to {analysis_path}")

    # Print summary
    print("")
    print("=== Analysis Complete ===")
    print(f"Batch:          {args.batch_name}")
    print(f"Tasks analyzed: {len(task_data)}")
    print(f"Models:         {', '.join(sorted(per_model.keys()))}")
    print(f"Categories:     easy={category_counts.get('easy', 0)}, "
          f"hard={category_counts.get('hard', 0)}, "
          f"discriminative={category_counts.get('discriminative', 0)}, "
          f"uncertain={category_counts.get('uncertain', 0)}")
    print(f"Report:         {report_path}")
    print(f"Analysis:       {analysis_path}")


if __name__ == "__main__":
    main()