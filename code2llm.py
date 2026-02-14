#!/usr/bin/env python3
"""
code2llm.py - A script to prepare code files for language model input.

This script collects code files from specified paths, respecting gitignore rules,
and formats them into a single output suitable for sending to a language model.
It automatically detects the programming languages of files and appends
language-specific system prompt additions for improved LLM understanding.
"""

import os
import argparse
import fnmatch
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Set

# ---------------------------------------------------------------------------
# Git and ignore logic
# ---------------------------------------------------------------------------

def find_git_root(path: str) -> Optional[Path]:
    """Finds the root of a Git repository starting from the given path."""
    current = Path(os.path.abspath(path))
    if current.is_file():
        current = current.parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").is_dir():
            return parent
    return None


def parse_gitignore(gitignore_path: str) -> List[str]:
    """Parses a .gitignore file and returns a list of patterns."""
    if not os.path.exists(gitignore_path):
        return []
    patterns = []
    try:
        with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                patterns.append(line)
    except OSError:
        pass
    return patterns


def gitignore_matches(rel_path: str, patterns: List[str]) -> bool:
    """Checks if a relative path matches any of the gitignore patterns."""
    for pattern in patterns:
        if pattern.startswith('!'):
            continue
        # Handle directory patterns
        if pattern.endswith('/'):
            if (rel_path + '/').startswith(pattern):
                return True
        # fnmatch works on path components, so we check the full path and the basename
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
            return True
    return False

# ---------------------------------------------------------------------------
# General prompt
# ---------------------------------------------------------------------------
BASE_SYSTEM_PROMPT = """
Act as an experienced senior software engineer. Generate clean, well-structured, production-ready code that follows current best practices and avoids deprecated APIs.

General requirements:
- I value your actions, not your words
- Save output tokens for important things, do not waste it by fluent phrases
- No flattery, no sycophancy
- If my idea or suggestion is complete nonsense, don't agree; let me know immediately if it's an anti-pattern or breaks any value
- I provide only a part of the codebase to focus on. If I forgot to paste a file required to complete an assignment, let me know immediately, do not assume its contents

Requirements:
- Code must be complete and ready to copy-paste without modifications: generate your output STRICTLY in one of two ways: 100% compatible git-diff patches OR the full source code containing changes; always include file name and hash (it could be fake) in diff
- For brevity it is acceptable to generate add-only part for tests and localization files, specify the line to where the add-on code shall be inserted 
- Consider all previous patches were applied when you've asked for a followup
- Use current, non-deprecated APIs and libraries
- Follow proper naming conventions and code organization
- Include error handling where appropriate
- Ensure code is performant and follows security best practices

Comments policy:
- Good code comments itself
- Comment code, not your actions
- Since I use git for change tracking, never add placeholder comments marking changes that has been made
- Only add comments that explain complex logic, algorithms, or non-obvious decisions
- Avoid obvious comments that simply restate what the code does
- Remember: good code should be self-documenting through clear naming and structure

Changes policy:
- Apply only and only requested changes and nothing else
- Avoid removing existing comments or reformatting non-changed parts of the code
- Follow the same coding and documentation style as it is in the modified file

If the requirements are unclear, ask for clarification rather than making assumptions.
"""

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

LANGUAGE_EXTENSIONS = {
    "python": [".py"],
    "cpp": [".cpp", ".hpp", ".cc", ".cxx", ".h", ".hh"],
    "java": [".java"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "csharp": [".cs"],
    "go": [".go"],
    "rust": [".rs"],
    "html": [".html", ".htm"],
    "css": [".css"],
    "shell": [".sh", ".bash"],
}


def detect_language(file_path: str) -> str:
    """Detects the programming language of a file based on its extension."""
    ext = os.path.splitext(file_path)[1].lower()
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        if ext in extensions:
            return lang
    return "unknown"

# ---------------------------------------------------------------------------
# Language-specific system prompts
# ---------------------------------------------------------------------------

LANGUAGE_PROMPTS = {
    "cpp": """C++ coding guidelines:
- Embrace RAII for all resource management. Use smart pointers (std::unique_ptr, std::shared_ptr) for dynamic memory and create your own RAII wrappers for other resource types.
- Prefer std::string_view for read-only string function parameters to avoid unnecessary copies and allocations.
- Favor composition and delegation over inheritance for more flexible and maintainable class designs.
- Use fixed-width integer types (e.g., int32_t) when the size is critical for correctness. For general-purpose, high-performance calculations, native types like int may be preferable.
- Avoid reinterpret_cast at all costs. Use static_cast for safe, compile-time checked conversions.
- Use auto to simplify code and improve maintainability, especially with complex types, but ensure the inferred type is clear from the context.
- Consider trailing return types (auto func() -> Type) to improve the readability of complex function declarations.
- Enforce const correctness by declaring variables and member functions const whenever they should not be modified.
- Replace macro-based logic with constexpr, inline functions, or templates.
- Eliminate magic numbers by using named constexpr variables to improve code clarity and maintainability.
- Use descriptive variable names. Short names are generally only acceptable for simple loop counters.
- Pass parameters by const reference for larger objects to avoid copies. For small or fundamental types, passing by value is often appropriate. Pass by non-const reference or pointer only when the function is intended to modify the argument.
""",
}


def gather_language_prompts(files: List[Tuple[str, Path]]) -> str:
    """Gathers language-specific prompts for the detected languages in the file list."""
    detected_langs = {detect_language(f[0]) for f in files}
    custom_prompts = []
    for lang in sorted(detected_langs):
        if lang in LANGUAGE_PROMPTS:
            custom_prompts.append(LANGUAGE_PROMPTS[lang])
    return "\n".join(custom_prompts)

# ---------------------------------------------------------------------------
# Exclusion system
# ---------------------------------------------------------------------------

class Excluder:
    """Handles logic for excluding files based on various patterns."""
    def __init__(self, base_paths: List[Path], exact_paths: List[str], regexes: List[str], substrings: List[str],
                 forced_exclude: List[str], forced_regexes: List[str], forced_substrings: List[str]):
        self.base_paths = base_paths or []
        self.regexes = [re.compile(r) for r in (regexes or [])]
        self.substrings = substrings or []
        self.forced_regexes = [re.compile(r) for r in (forced_regexes or [])]
        self.forced_substrings = forced_substrings or []
        self.forced_exclude = set()
        for p in (forced_exclude or []):
            if os.path.isabs(p):
                self.forced_exclude.add(os.path.normpath(p))
            else:
                for b in self.base_paths:
                    self.forced_exclude.add(os.path.normpath(str(b / p)))

        self.exact_prefixes: Set[str] = set()
        for p in (exact_paths or []):
            if os.path.isabs(p):
                self.exact_prefixes.add(os.path.normpath(p))
            else:
                for b in self.base_paths:
                    self.exact_prefixes.add(os.path.normpath(str(b / p)))

    def is_excluded(self, path: str, base_path: Optional[Path]) -> bool:
        """Checks if a file matches the standard exclusion rules."""
        norm = os.path.normpath(path)
        for pref in self.exact_prefixes:
            if norm == pref or norm.startswith(pref + os.sep):
                return True
        for rx in self.regexes:
            try:
                if rx.search(norm):
                    return True
            except re.error:
                return False
        rel = os.path.relpath(norm, str(base_path)) if base_path else norm
        base_name = os.path.basename(norm)
        for sub in self.substrings:
            if sub in norm or sub in rel or sub in base_name:
                return True
        return False

    def is_forced_excluded(self, path: str) -> bool:
        """Checks if a file matches the forced exclusion rules (removes from structure)."""
        norm = os.path.normpath(path)
        for fe in self.forced_exclude:
            if norm == fe or norm.startswith(fe + os.sep):
                return True
        for rx in self.forced_regexes:
            try:
                if rx.search(norm):
                    return True
            except re.error:
                return False
        for sub in self.forced_substrings:
            if sub in norm:
                return True
        return False

# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_files(input_paths: List[str], excluder: Excluder) -> List[Tuple[str, Path]]:
    """Collects all files from input paths, respecting .gitignore and excluder rules."""
    all_files: List[Tuple[str, Path]] = []
    for input_path_str in input_paths:
        input_path = Path(input_path_str).resolve()
        git_root = find_git_root(str(input_path))
        base_path = git_root or (input_path.parent if input_path.is_file() else input_path)

        gitignore_patterns = parse_gitignore(str(base_path / '.gitignore')) if git_root else []

        if input_path.is_file():
            rel_path = input_path.relative_to(base_path).as_posix()
            if not gitignore_matches(rel_path, gitignore_patterns):
                all_files.append((str(input_path), base_path))
            continue

        for root, dirs, files in os.walk(str(input_path)):
            root_path = Path(root)
            rel_root = root_path.relative_to(base_path).as_posix()

            # Filter directories based on gitignore and exclusion rules
            filtered_dirs = []
            for d in dirs:
                dir_path = root_path / d
                dir_rel_path = f"{rel_root}/{d}" if rel_root else d

                # Skip if gitignore matches
                if gitignore_matches(dir_rel_path, gitignore_patterns):
                    continue

                # Skip if force excluded
                if excluder.is_forced_excluded(str(dir_path)):
                    continue

                # Skip if excluded (don't traverse, but would show in structure)
                if excluder.is_excluded(str(dir_path), base_path):
                    continue

                filtered_dirs.append(d)

            dirs[:] = filtered_dirs

            for file in files:
                file_path = root_path / file
                rel_path = file_path.relative_to(base_path).as_posix()

                if gitignore_matches(rel_path, gitignore_patterns):
                    continue
                # A simple check to avoid adding files from the .git directory
                if '/.git/' in file_path.as_posix():
                    continue

                all_files.append((str(file_path), base_path))

    # Sort and remove duplicates
    all_files = sorted(list(set(all_files)), key=lambda x: x[0])
    return all_files

# ---------------------------------------------------------------------------
# PROJECT STRUCTURE formatting + file output
# ---------------------------------------------------------------------------

def format_output(all_files: List[Tuple[str, Path]], excluder: Excluder, include_system_prompt: bool, include_structure: bool) -> str:
    """Formats the final output string with structure and file contents."""
    parts: List[str] = []

    included_files: List[Tuple[str, Path]] = []
    structure_lines: List[str] = []

    # First, determine which files are included, excluded, or force-excluded
    # This loop builds the project structure and populates the included_files list
    if include_structure:
        file_index = 1
        for fp, base in all_files:
            if excluder.is_forced_excluded(fp):
                continue

            rel_path = Path(fp).relative_to(base).as_posix()

            if excluder.is_excluded(fp, base):
                structure_lines.append(f"[x] {rel_path}")
            else:
                structure_lines.append(f"[{file_index}] {rel_path}")
                included_files.append((fp, base))
                file_index += 1

    # If structure is disabled, all non-force-excluded files are considered "included"
    else:
        for fp, base in all_files:
            if not excluder.is_forced_excluded(fp) and not excluder.is_excluded(fp, base):
                included_files.append((fp, base))

    # --- Start building the output ---

    if include_system_prompt:
        parts.append(BASE_SYSTEM_PROMPT)
        # Language prompts are based ONLY on included files
        lang_section = gather_language_prompts(included_files)
        if lang_section:
            parts.append(lang_section)

    if include_structure and structure_lines:
        parts.append("PROJECT STRUCTURE:")
        parts.extend(structure_lines)

    # Append full file contents ONLY for included files
    if included_files:
        parts.append("\n--- FILE CONTENTS ---\n")
        for idx, (fp, base) in enumerate(included_files, start=1):
            rel = Path(fp).relative_to(base).as_posix()
            try:
                with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception as e:
                content = f"__UNREADABLE__ ({e})"
            parts.append(f"### [{idx}] {rel}\n```\n{content}\n```\n")

    return "\n".join(parts)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Prepare code files for language model input.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-i', '--input', action='append',
                        help='Input paths (files or directories). Can be specified multiple times.\nDefault is current directory.')
    parser.add_argument('-e', '--exclude', action='append', default=[],
                        help='Exclude a path. Will be marked with [x] in the structure and omitted from contents.\nCan be specified multiple times.')
    parser.add_argument('-er', '--exclude-regex', action='append', default=[],
                        help='Exclude files matching a regex. Marked with [x]. Can be specified multiple times.')
    parser.add_argument('-ex', '--exclude-substr', action='append', default=[],
                        help='Exclude files containing a substring in their path. Marked with [x].\nCan be specified multiple times.')
    parser.add_argument('-ef', '--exclude-force', action='append', default=[],
                        help='Force exclude a path. It will NOT appear in the project structure at all.\nCan be specified multiple times.')
    parser.add_argument('-erf', '--exclude-regex-force', action='append', default=[],
                        help='Force exclude files matching a regex. Will NOT appear in the project structure at all.\nCan be specified multiple times.')
    parser.add_argument('-exf', '--exclude-substr-force', action='append', default=[],
                        help='Force exclude files containing a substring in their path. Will NOT appear in the project structure at all.\nCan be specified multiple times.')
    parser.add_argument('--no-system-prompt', action='store_true',
                        help='Do not include the system prompt in the output.')
    parser.add_argument('--no-structure', action='store_true',
                        help='Do not include the PROJECT STRUCTURE list in the output.')
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()
    inputs = args.input if args.input else ['.']

    # Determine base paths for relative path calculations
    base_paths: List[Path] = []
    for inp in inputs:
        gr = find_git_root(inp)
        if gr and gr not in base_paths:
            base_paths.append(gr)
    if not base_paths:
        base_paths = [Path.cwd()]

    excluder = Excluder(base_paths, args.exclude, args.exclude_regex, args.exclude_substr,
                        args.exclude_force, args.exclude_regex_force, args.exclude_substr_force)

    all_files = collect_files(inputs, excluder)

    # Filter out binary files before formatting
    filtered_files: List[Tuple[str, Path]] = []
    for fp, base in all_files:
        try:
            with open(fp, 'rb') as fh:
                # A simple check for null bytes in the first 4KB is a decent heuristic for binary files
                if b'\x00' in fh.read(4096):
                    continue
        except Exception:
            continue
        filtered_files.append((fp, base))

    output = format_output(filtered_files, excluder, not args.no_system_prompt, not args.no_structure)

    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.buffer.write(output.encode('utf-8'))
    else:
        print(output)


if __name__ == "__main__":
    main()
