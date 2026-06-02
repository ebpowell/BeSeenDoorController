#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
my_venv/bin/python3 -m unittest discover tests
