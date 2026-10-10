"""
CLI Entry point for the Intelligent Agentic Coding System.
Allows developers to send any coding prompt to the Claude Opus + Gemini Flash multi-model pipeline.
Usage:
    python scripts/agentic_coder.py --prompt "Create a thread-safe LRU cache with TTL in services/lru_cache.py"
"""
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from services.agentic_orchestrator import AgenticCodingOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Intelligent Dual-LLM Agentic Coding CLI")
    parser.add_argument("--prompt", type=str, required=True, help="Coding prompt or feature specification")
    parser.add_argument("--out", type=str, default=None, help="Optional output file path to write generated code")
    parser.add_argument("--target-files", nargs="*", default=None, help="Specific workspace files to include as context")
    args = parser.parse_args()

    print("\n[LAUNCH] Launching Agentic AI Coding Pipeline...")
    print(f"Prompt: {args.prompt}\n")

    orchestrator = AgenticCodingOrchestrator()
    result = orchestrator.process_prompt(prompt=args.prompt, target_files=args.target_files)

    print("=" * 60)
    for stage in result["stages"]:
        print(f"\n-> [{stage['stage']}]")
        print(f"   Model: {stage['model_used']} ({stage['provider']})")
        print("-" * 40)
        output_snippet = (stage['output'] or '')[:300].replace('\n', ' ')
        print(f"   Output: {output_snippet}...\n")

    print("=" * 60)
    print("\n[FINAL GENERATED CODE]:\n")
    print(result["final_code"][:1000] + ("\n..." if len(result["final_code"]) > 1000 else ""))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result["final_code"])
        print(f"\n[SAVED] Saved generated code to: {out_path}")


if __name__ == "__main__":
    main()
