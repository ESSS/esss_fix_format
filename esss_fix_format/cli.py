# -*- coding: utf-8 -*-
import io
import os
import sys

import click
import subprocess

ISORT_CONFIG = {
    'line_length': 100,
    'multi_line_output': 4,  # 4-vert-grid
}

EXTENSIONS = {'.py', '.cpp', '.c', '.h', '.hpp', '.hxx', '.cxx', '.java', '.js'}


@click.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True, dir_okay=False, writable=True))
@click.option('--check', default=False, is_flag=True, help='check instead of formatting files')
@click.option('--stdin', default=False, is_flag=True, help='read filenames from stdin (1 per line)')
@click.option('-c', '--commit', default=False, is_flag=True, help='use modified files from git')
def main(files, check, stdin, commit):
    """Console script for esss_fix_format"""
    import isort
    if stdin:
        files = [x.strip() for x in click.get_text_stream('stdin').readlines()]
    if commit:
        files = get_files_from_git()
    changed_files = 0
    for filename in files:
        extension = os.path.splitext(filename)[1]
        if extension in EXTENSIONS:
            with io.open(filename, 'rb') as f:
                old_contents = f.read().decode('UTF-8')
            if extension == '.py':
                new_contents = isort.SortImports(file_contents=old_contents, **ISORT_CONFIG).output
            else:
                new_contents = old_contents
            new_contents = fix_whitespace(new_contents)
            changed = new_contents != old_contents
        else:
            click.secho(click.format_filename(filename) + ': Unknown extension', fg='white')
            continue
        if not check and changed:
            with io.open(filename, 'wb') as f:
                f.write(new_contents.encode('UTF-8'))
        changed_files += int(changed)
        status, color = _get_status_and_color(check, changed)
        click.secho(click.format_filename(filename) + ': ' + status, fg=color)

    if check and changed_files:
        sys.exit(1)


def _get_status_and_color(check, changed):
    """
    Return a pair (status message, color) based if we are checking a file for correct formatting and if
    the file is supposed to be changed or not.
    """
    if check:
        if changed:
            return 'Failed', 'red'
        else:
            return 'OK', 'green'
    else:
        if changed:
            return 'Fixed', 'green'
        else:
            return 'Skipped', 'yellow'


def fix_whitespace(old_contents):
    """
    Fix whitespace issues in the given list of lines.

    :param unicode old_contents:
        List of lines to fix spaces and indentations.

    :return unicode:
        Returns the new contents.
    """
    input_lines = old_contents.split('\n')
    lines = [i.rstrip('\r') for i in input_lines]
    lines = _right_trim_spaces(lines)
    lines = _fix_tabs(lines)
    contents = '\n'.join(lines)
    return contents



def _right_trim_spaces(lines):
    """
    Remove spaces from the right side of each line.

    :param list(unicode) lines:
        Input lines.

    :return list(unicode):
        Modified lines.
    """
    return [i.rstrip(' \t') for i in lines]


def _fix_tabs(lines, tab_width=4):
    """
    Expands tab characters in the given list of lines for spaces..

    :param list(unicode) lines:
        Input lines.

    :return list(unicode):
        Modified lines.
    """
    return [i.expandtabs(tab_width) for i in lines]


def get_files_from_git():
    """Obtain from a list of modified files in the current repository."""
    def get_files(cmd):
        output = subprocess.check_output(cmd, shell=True)
        return output.splitlines()

    result = set()
    result.update(get_files('git diff --name-only --diff-filter=ACM --staged'))
    result.update(get_files('git diff --name-only --diff-filter=ACM'))
    result.update(get_files('git ls-files -o --full-name --exclude-standard'))
    return sorted(result)


if __name__ == "__main__":
    main()
