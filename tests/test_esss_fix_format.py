#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
    source = textwrap.dedent(
        r'''\
            alpha
            bravo\s\t\s
            charlie
            \tdelta
            echo\r
            foxtrot
            golf #Comment
            hotel
        '''.replace('\s', ' ').replace(r'\t', '\t').replace(r'\r', '\r').replace(r'\n', '\n')
    )
    filename = tmpdir.join('test.py')
    filename.write(source)
    return filename


def test_command_line_interface(input_file):
    check_invalid_file(input_file)
    fix_invalid_file(input_file)

    check_valid_file(input_file)
    fix_valid_file(input_file)


@pytest.mark.xfail(reason='this is locking up during main(), although it works on the cmdline', run=False)
def test_stdin_input(input_file):
    runner = CliRunner()
    result = runner.invoke(cli.main, args=['--stdin'], input=str(input_file) + '\n')
    assert result.exit_code == 0
    assert str(input_file) in result.output


def test_fix_format(input_file):
    input_contents = input_file.read()
    obtained = cli.fix_format(str(input_contents))
    expected = textwrap.dedent(
        r'''\
            alpha
            bravo
            charlie
            \s\s\s\sdelta
            echo
            foxtrot
            golf #Comment
            hotel
        '''.replace(r'\s', ' ')
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
    filename.write(source.encode('UTF-8'), 'wb')

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
    assert filename.read('rb').decode('UTF-8') == expected


def test_unknown_extension(input_file):
    new_filename = py.path.local(os.path.splitext(str(input_file))[0] + '.unknown')
    input_file.move(new_filename)
    output = run(['--check', str(new_filename)], expected_exit=0)
    output.fnmatch_lines(str(new_filename) + ': Unknown extension')

    output = run([str(new_filename)], expected_exit=0)
    output.fnmatch_lines(str(new_filename) + ': Unknown extension')


@pytest.mark.parametrize('param', ['-c', '--commit'])
def test_fix_commit(input_file, mocker, param):
    m = mocker.patch.object(subprocess, 'check_output', return_value=str(input_file) + '\n')
    output = run([param], expected_exit=0)
    output.fnmatch_lines(str(input_file) + ': Fixed')
    assert m.call_args_list == [
        mock.call('git diff --name-only --diff-filter=ACM --staged', shell=True),
        mock.call('git diff --name-only --diff-filter=ACM', shell=True),
        mock.call('git ls-files -o --full-name --exclude-standard', shell=True),
    ]


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