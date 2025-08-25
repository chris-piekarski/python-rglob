import argparse
import os
from rglob import rglob, lcount, tsize, kilobytes, megabytes, gigabytes, terabytes

def main():
    parser = argparse.ArgumentParser(
        description="Recursive file operations.",
        epilog=(
            "Note: Quote or escape glob patterns so your shell doesn't pre-expand "
            "them. For example, use \"*.py\" (with quotes), not *.py."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Find command
    find_parser = subparsers.add_parser("find", help="Find files recursively.")
    find_parser.add_argument("pattern", help="The glob pattern to match.")
    find_parser.add_argument("--base", default=os.getcwd(), help="The base directory to search in.")

    # Line count command
    lcount_parser = subparsers.add_parser("lcount", help="Count lines in files recursively.")
    lcount_parser.add_argument("pattern", help="The glob pattern to match.")
    lcount_parser.add_argument("--base", default=os.getcwd(), help="The base directory to search in.")
    lcount_parser.add_argument("--no-empty", action="store_true", help="Exclude empty lines.")
    lcount_parser.add_argument("--no-comments", action="store_true", help="Exclude comment lines (starting with #).")

    # Total size command
    tsize_parser = subparsers.add_parser("tsize", help="Calculate the total size of files recursively.")
    tsize_parser.add_argument("pattern", help="The glob pattern to match.")
    tsize_parser.add_argument("--base", default=os.getcwd(), help="The base directory to search in.")
    tsize_parser.add_argument("--unit", default="mb", choices=["kb", "mb", "gb", "tb"], help="The unit to display the size in.")

    args = parser.parse_args()

    if args.command == "find":
        files = rglob(args.base, args.pattern)
        for f in files:
            print(f)
    elif args.command == "lcount":
        filter_funcs = []
        if args.no_empty:
            filter_funcs.append(lambda line: line.strip())
        if args.no_comments:
            filter_funcs.append(lambda line: not line.strip().startswith("#"))
        
        def combined_filter(line):
            return all(f(line) for f in filter_funcs)

        count = lcount(args.base, args.pattern, func=combined_filter if filter_funcs else lambda x: True)
        print(f"Total lines: {count}")
    elif args.command == "tsize":
        unit_funcs = {
            "kb": kilobytes,
            "mb": megabytes,
            "gb": gigabytes,
            "tb": terabytes,
        }
        total_size = tsize(args.base, args.pattern, func=unit_funcs[args.unit])
        print(f"Total size: {total_size:.2f} {args.unit.upper()}")

if __name__ == "__main__":
    main()
