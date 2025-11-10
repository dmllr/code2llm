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
import glob
import fnmatch
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Git and ignore logic
# ---------------------------------------------------------------------------

def find_git_root(path):
    """Find the git repository root for a given path."""
    current = Path(os.path.abspath(path))
    if os.path.isfile(current):
        current = current.parent
    while current != current.parent:
        if (current / ".git").is_dir():
            return current
        current = current.parent
    return None


def parse_gitignore(gitignore_path):
    """Parse a .gitignore file and return a list of patterns."""
    if not os.path.exists(gitignore_path):
        return []
    patterns = []
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            patterns.append(line)
    return patterns


def should_ignore(path, base_path, gitignore_patterns):
    """Check if a path should be ignored based on gitignore patterns."""
    rel_path = os.path.relpath(path, base_path)
    for pattern in gitignore_patterns:
        if pattern.startswith('!'):
            continue
        if pattern.endswith('/'):
            if os.path.isdir(path) and fnmatch.fnmatch(rel_path + '/', pattern):
                return True
        elif fnmatch.fnmatch(rel_path, pattern):
            return True
        elif '/' not in pattern and fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False


def should_exclude(path, base_path, exclude_patterns):
    """Check if a path should be excluded based on user-provided patterns."""
    rel_path = os.path.relpath(path, base_path)
    for pattern in exclude_patterns:
        if '*' in pattern:
            regex_pattern = fnmatch.translate(pattern)
            if re.match(regex_pattern, rel_path) or re.match(regex_pattern, os.path.basename(path)):
                return True
        elif rel_path.startswith(pattern):
            return True
    return False


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

def collect_files(input_paths, exclude_patterns):
    """Collect files from input paths respecting gitignore and exclusion rules."""
    all_files = []
    for input_path in input_paths:
        input_path = os.path.abspath(input_path)
        git_root = find_git_root(input_path)
        if git_root is None:
            base_path = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
            gitignore_patterns = []
        else:
            base_path = git_root
            gitignore_patterns = parse_gitignore(os.path.join(git_root, '.gitignore'))

        if os.path.isfile(input_path):
            if (not should_ignore(input_path, base_path, gitignore_patterns) and
                    not should_exclude(input_path, base_path, exclude_patterns)):
                all_files.append((input_path, base_path))
        else:
            for root, dirs, files in os.walk(input_path):
                dirs_to_remove = []
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    if (should_ignore(dir_path, base_path, gitignore_patterns) or
                            should_exclude(dir_path, base_path, exclude_patterns)):
                        dirs_to_remove.append(d)
                for d in dirs_to_remove:
                    dirs.remove(d)
                for file in files:
                    file_path = os.path.join(root, file)
                    if (not should_ignore(file_path, base_path, gitignore_patterns) and
                            not should_exclude(file_path, base_path, exclude_patterns)):
                        all_files.append((file_path, base_path))
    return all_files


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


def detect_language(file_path):
    """Detect the programming language based on file extension."""
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
- Pass parameters by const reference for larger objects to avoid copies. For small or fundamental types, passing by value is often appropriate. Pass by non-const reference or pointer only when the function is intended to modify the argument.""",
}


def gather_language_prompts(files):
    """Gather unique language-specific prompts from the detected files."""
    detected_langs = {detect_language(f[0]) for f in files}
    custom_prompts = []
    for lang in sorted(detected_langs):
        if lang in LANGUAGE_PROMPTS:
            custom_prompts.append(LANGUAGE_PROMPTS[lang])
    return "\n".join(custom_prompts)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def build_file_tree(files):
    """Build a tree structure of the files for display."""
    tree = {}
    for file_path, base_path in files:
        rel_path = os.path.relpath(file_path, base_path)
        parts = rel_path.split(os.sep)
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = None
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
    return tree


def print_tree(tree, prefix="", is_last=True, output_lines=None):
    """Print the tree structure using ASCII characters."""
    if output_lines is None:
        output_lines = []
    items = list(tree.items())
    for i, (name, subtree) in enumerate(items):
        is_last_item = i == len(items) - 1
        if prefix:
            output_lines.append(f"{prefix}{'`-- ' if is_last_item else '|-- '}{name}")
        else:
            output_lines.append(name)
        if subtree is not None:
            extension = "    " if is_last_item else "|   "
            print_tree(subtree, prefix + extension, is_last_item, output_lines)
    return output_lines


def format_output(files):
    """Format collected files for language model input."""
    base_system_prompt = """Act as an experienced senior software engineer. Generate clean, well-structured, production-ready code that follows current best practices and avoids deprecated APIs.

General requirements:
- I value your actions, not your words
- Save output tokens for important things, do not waste it by fluent phrases
- No flattery, no sycophancy
- If my idea or suggestion is complete nonsense, don't reply, "it's a great idea"; let me know immediately if it's an anti-pattern or breaks any value 

Requirements:
- Code must be complete and ready to copy-paste without modifications
- Git-compatible patches are acceptable for small changes of big files; assume all previous patches were applied when you've asked to generate a followup patch 
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

    # Add custom language-specific sections
    language_section = gather_language_prompts(files)
    if language_section:
        base_system_prompt += "\n"
        base_system_prompt += language_section

    output = base_system_prompt + "\n\n"

    # Add file tree
    file_tree = build_file_tree(files)
    for line in print_tree(file_tree):
        output += line + "\n"
    output += "\n"

    # Append each file content
    for file_path, base_path in files:
        rel_path = os.path.relpath(file_path, base_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            output += f"{rel_path}:\n```\n{content}\n```\n\n"
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Prepare code files for language model input.')
    parser.add_argument('-i', '--input', action='append', default=None,
                        help='Input paths (files or directories). Can be specified multiple times. Default is current directory.')
    parser.add_argument('-e', '--exclude', action='append', default=[],
                        help='Patterns to exclude. Can be specified multiple times.')
    args = parser.parse_args()

    if args.input is None:
        args.input = ['.']

    files = collect_files(args.input, args.exclude)
    output = format_output(files)

    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.buffer.write(output.encode('utf-8'))
    else:
        print(output)


if __name__ == "__main__":
    main()
