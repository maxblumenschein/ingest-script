import os

# Get the directory of the script
script_dir = os.path.dirname(__file__)

match = open(os.path.join(script_dir, 'medienstandard-kategorien.txt')).read().splitlines()
