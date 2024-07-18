import os

# Get the directory of the script
script_dir = os.path.dirname(__file__)

# Define file-check-lists
first_characters = open(os.path.join(script_dir, 'medienstandard-zustaendigkeit.txt')).read().splitlines()
second_forth_characters = open(os.path.join(script_dir, 'medienstandard-kategorien.txt')).read().splitlines()
