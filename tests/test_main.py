import pytest
from src.main import main
from io import StringIO
import sys
import runpy

def test_main(capsys):
    # Capture the output of the main function
    main()
    captured = capsys.readouterr()
    assert captured.out == "Hello World!\n"

def test_main_as_script(capsys):
    # Simulate running the script as the main module
    runpy.run_module("src.main", run_name="__main__")
    captured = capsys.readouterr()
    assert captured.out == "Hello World!\n"