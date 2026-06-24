#!/bin/bash
cd /home/efrain/Projects/Analisis_Concursos_DAFO
.venv/bin/python -u server.py &
echo $! > /tmp/dafo.pid
wait