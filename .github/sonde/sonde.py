"""Sonde temporaire : collecteur des radios privées sur les vrais sites (RMC, Radio Classique ajoutées)."""
import subprocess
import sys

# Le journal ne garde que la fin de la sortie.
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "collecter-radio", "--motifs"])
subprocess.run([sys.executable, "-m", "grille", "--base", "/tmp/sonde.sqlite", "douteux", "--nombre", "80"])
