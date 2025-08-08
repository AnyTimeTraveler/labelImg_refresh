#!/usr/bin/env sh

pyrcc5 resources.qrc -o resources.py
pyrcc5 -o libs/resources.py resources.qrc
