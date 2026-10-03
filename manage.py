#!/usr/bin/env python
"""Entrada de los comandos de Django de EVALUON."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evaluon.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
