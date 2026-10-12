"""Sonde temporaire : collecteur des radios privées sur les vrais sites."""
import subprocess
import sys

subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "collecter-radio", "--motifs"])
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "douteux", "--nombre", "50"])
