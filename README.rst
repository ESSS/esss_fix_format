===============================
esss_fix_format
===============================


.. image:: https://img.shields.io/travis/esss/esss_fix_format.svg
        :target: https://travis-ci.org/esss/esss_fix_format


Simple code formatter and pre-commit checker used internally by ESSS.

* Imports sorted using `isort <https://pypi.python.org/pypi/isort>`_;
* Trim right spaces;
* Expand tabs;

* Free software: MIT license


Usage
-----

This repository provides a tool ``fix-format`` (or ``ff`` for short) which can be used to format files automatically
or check if some files are already formatted (usually in a ``pre-commit`` hook).

1. To manually format files and/or directories::

    fix-format <file1> <dir1> ...


2. Format modified files in Git::

    fix-format --commit

   Or more succinctly::

    ff -c

3. Use as Git hook:

.. code-block:: bash

    if ! git diff-index --name-only --cached $against | ff --check --stdin
    then
        exit 1
    fi


Credits
---------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage

