#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import os
import subprocess
import textwrap

import mock
import py
import pytest
from click.testing import CliRunner

from esss_fix_format import cli


@pytest.fixture
def input_file(tmpdir):
    # imports out-of-order included in example so isort detects as necessary to change
    source = textwrap.dedent(
        '''\
            import sys
            import os

            alpha
            bravo\\s\\t\\s
            charlie
            \\tdelta
            echo
            foxtrot
            golf #Comment
            hotel
        '''.replace('\\s', ' ').replace('\\t', '\t')
    )
    filename = tmpdir.join('test.py')
    filename.write(source)
    return filename


def test_command_line_interface(input_file):
    check_invalid_file(input_file)
    fix_invalid_file(input_file)

    check_valid_file(input_file)
    fix_valid_file(input_file)


@pytest.mark.parametrize(
    'eol',
    [
        '\n',
        '\r\n',
        '\r'
    ],
    ids=[
        'lf',
        'crlf',
        'cr'
    ]
)
def test_input_eol_preserved(input_file, eol):
    contents = input_file.read('r')
    contents = contents.replace('\n', eol)
    input_file.write(contents.encode('ascii'), 'wb')
    check_invalid_file(input_file)
    fix_invalid_file(input_file)

    for line in io.open(str(input_file), newline='').readlines():
        assert line.endswith(eol)


def test_directory_command_line(input_file, tmpdir):
    another_file = tmpdir.join('subdir', 'test2.py').ensure(file=1)
    input_file.copy(another_file)

    output = run([str(tmpdir)], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ': Fixed')
    output.fnmatch_lines(str(another_file) + ': Fixed')


@pytest.mark.xfail(reason='this is locking up during main(), but works on the cmdline', run=False)
def test_stdin_input(input_file):
    runner = CliRunner()
    result = runner.invoke(cli.main, args=['--stdin'], input=str(input_file) + '\n')
    assert result.exit_code == 0
    assert str(input_file) in result.output


def test_fix_whitespace(input_file):
    obtained = cli.fix_whitespace(input_file.readlines(), eol='\n', ends_with_eol=True)
    expected = textwrap.dedent(
        '''\
            import sys
            import os

            alpha
            bravo
            charlie
            \\s\\s\\s\\sdelta
            echo
            foxtrot
            golf #Comment
            hotel
        '''.replace('\\s', ' ')
    )
    assert obtained == expected


def test_imports(tmpdir):
    source = textwrap.dedent('''\
        import pytest
        import sys

        import io
        # my class
        class Test:
            pass
    ''')
    filename = tmpdir.join('test.py')
    filename.write(source, 'w')

    check_invalid_file(str(filename))
    fix_invalid_file(str(filename))

    expected = textwrap.dedent('''\
        import io
        import sys

        import pytest


        # my class
        class Test:
            pass
    ''')
    assert filename.read('r') == expected


def test_unknown_extension(input_file):
    new_filename = py.path.local(os.path.splitext(str(input_file))[0] + '.unknown')
    input_file.move(new_filename)
    output = run(['--check', str(new_filename)], expected_exit=0)
    output.fnmatch_lines(str(new_filename) + ': Unknown extension')

    output = run([str(new_filename)], expected_exit=0)
    output.fnmatch_lines(str(new_filename) + ': Unknown extension')


@pytest.mark.parametrize('param', ['-c', '--commit'])
def test_fix_commit(input_file, mocker, param, tmpdir):

    def check_output(cmd, *args, **kwargs):
        if '--show-toplevel' in cmd:
            return str(tmpdir) + '\n'
        else:
            return input_file.basename + '\n'

    m = mocker.patch.object(subprocess, 'check_output', side_effect=check_output)
    output = run([param], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ': Fixed')
    assert m.call_args_list == [
        mock.call('git rev-parse --show-toplevel', shell=True),
        mock.call('git diff --name-only --diff-filter=ACM --staged', shell=True),
        mock.call('git diff --name-only --diff-filter=ACM', shell=True),
        mock.call('git ls-files -o --full-name --exclude-standard', shell=True),
    ]


def test_input_invalid_codec(tmpdir):
    """Display error summary when we fail to open a file"""
    filename = tmpdir.join('test.py')
    filename.write(u'hello world'.encode('UTF-16'), 'wb')
    output = run([str(filename)], expected_exit=1)
    output.fnmatch_lines(str(filename) + ': ERROR (Unicode*')
    output.fnmatch_lines('*== ERRORS ==*')
    output.fnmatch_lines(str(filename) + ': ERROR (Unicode*')


def test_empty_file(tmpdir):
    """Ensure files with a single empty line do not raise an error"""
    filename = tmpdir.join('test.py')
    filename.write(u'\r\n', 'w')
    run([str(filename)], expected_exit=0)


def test_skip_entire_file(tmpdir):
    """Check that a module-level isort:skip_file correctly skips that file"""
    source = textwrap.dedent('''\
        """
        isort:skip_file
        """
        import sys
    ''')
    filename = tmpdir.join('test.py')
    filename.write(source)
    output = run([str(filename)], expected_exit=0)
    output.fnmatch_lines(str(filename) + ': Skipped')
    assert filename.read() == source


@pytest.mark.xfail(reason='isort 4.2.5 bug, see timothycrosley/isort#460', strict=True)
def test_isort_bug_with_comment_headers(tmpdir):
    source = textwrap.dedent("""\
        '''
        See README.md for usage.
        '''
        import os

        #===============================
        # Ask
        #===============================
        import io


        def Ask(question, answers):
            pass
    """)
    filename = tmpdir.join('test.py')
    filename.write(source)
    check_invalid_file(filename)
    fix_invalid_file(filename)
    check_valid_file(filename)


def test_missing_builtins(tmpdir):
    source = textwrap.dedent("""\
        import thirdparty
        import os
        import ftplib
        import numbers
    """)
    filename = tmpdir.join('test.py')
    filename.write(source)
    check_invalid_file(filename)
    fix_invalid_file(filename)
    check_valid_file(filename)
    obtained = filename.read()
    assert obtained == textwrap.dedent("""\
        import ftplib
        import numbers
        import os

        import thirdparty
    """)


def run(args, expected_exit):
    from _pytest.pytester import LineMatcher
    runner = CliRunner()
    result = runner.invoke(cli.main, args)
    msg = 'exit code %d != %d.\nOutput: %s' % (result.exit_code, expected_exit, result.output)
    assert result.exit_code == expected_exit, msg
    return LineMatcher(result.output.splitlines())


def fix_valid_file(input_file):
    output = run([str(input_file)], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ': Skipped')


def check_valid_file(input_file):
    output = run(['--check', str(input_file)], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ': OK')


def fix_invalid_file(input_file):
    output = run([str(input_file)], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ': Fixed')


def check_invalid_file(input_file):
    output = run(['--check', str(input_file)], expected_exit=1)
    output.fnmatch_lines(str(input_file) + ': Failed')
    output.fnmatch_lines('*== failed checks ==*')
    output.fnmatch_lines(str(input_file))
