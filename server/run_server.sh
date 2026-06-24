#!/bin/bash
cd /home/efrain/Projects/Analisis_Concursos_DAFO
exec .venv/bin/python server.py > /tmp/server.log 2>&1
