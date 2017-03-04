#!/usr/bin/env python2
#coding: UTF-8
import subprocess
import os
import zlib
import argparse
import json
import re
import textract
import hashlib
import sys
from time import time


INDEX_PATH = os.path.expanduser("~/.pdfindex")

"""
Index is zlib of json:
hash is sha256

files[filename]:
	hash
	modified: modified time
hashs[hash]:
	txt from pdf file
"""

# Parse a pdf file and returns containing text.
def pdf_to_text(fname):
	# TODO faster alternative?
	t = textract.process(fname)
	for c,u in zip("aouAOU", ["ä","ö","ü","Ä","Ö","Ü"]):
		t = t.replace("%s\xcc\x88" % c, u)
	return t
	# return subprocess.check_output(['ps2ascii', fname])

def hash_file(fname):
	d = open(fname, "rb").read()
	return hashlib.sha256(d).hexdigest()

# Recurse given rootdir and adds new files to index.
def dir_to_index(index, rootdir, instant_save=False):
	cwd = os.path.abspath(rootdir)
	file_list = []

	for root, subdirs, files in os.walk(cwd):
		for fname in files:
			if not fname.endswith(".pdf"):
				continue
			fname = os.path.join(cwd, root, fname)
			if need_update(index, fname):
				file_list.append(fname)

	last_save = time()
	# TODO do this threaded?
	for i,fname in enumerate(file_list):
		print >> sys.stderr, "[%s/%s] %s" % (i+1, len(file_list), os.path.relpath(fname,rootdir))
		add_file_to_index(index, fname)

		if instant_save and time() > last_save + 10:
			# TODO make atomic
			save_index(INDEX_PATH, index)
			last_save = time()

	return index

# Returns true, iff the file needs to be updated in index.
def need_update(index, fname):
	if not fname.endswith(".pdf"):
		return False
	fname = os.path.abspath(fname).decode("utf8")

	if not os.path.isfile(fname):
		return False

	if not fname in index["files"]:
		return True

	if os.path.getmtime(fname) != index["files"][fname]["modified"]:
		return True

	return False

# Checks if the given file (fname) needs to be updated in the index
# and, if needed, do this.
def add_file_to_index(index, fname):
	if not fname.endswith(".pdf"):
		return
	fname = os.path.abspath(fname)

	if not os.path.isfile(fname):
		if fname in index["files"]:
			del index["files"][fname]
		return

	if fname in index["files"]:
		if os.path.getmtime(fname) == index["files"][fname]["modified"]:
			return

		h = hash_file(fname)

		index["files"][fname]["modified"] = os.path.getmtime(fname)
		if index["files"][fname]["hash"] != h:
			index["files"][fname]["hash"] = h
			index["hashs"][h] = pdf_to_text(fname)

	else:
		h = hash_file(fname)
		index["files"][fname] = {}
		index["files"][fname]["hash"] = h
		index["files"][fname]["modified"] = os.path.getmtime(fname)
		if not h in index["hashs"]:
			index["hashs"][h] = pdf_to_text(fname)


# saves the index to file
def save_index(fname, index):
	# TODO atomic/backup?
	d = zlib.compress(json.dumps(index))
	open(fname, "wb").write(d)

# loads the index from given file
def load_index(fname, parse_files=False):
	if not os.path.isfile(fname):
		return {"files": {}, "hashs": {}}

	d = open(fname, "rb").read()
	index = json.loads(zlib.decompress(d))
	if parse_files:
		for fname in index["files"].keys():
			add_file_to_index(index, fname)

	return index

class Color:
	RED     = '\033[91m'
	RED2    = '\033[1;91m'
	GREEN   = '\033[92m'
	GREEN2  = '\033[1;92m'
	YELLOW  = '\033[93m'
	YELLOW2 = '\033[1;93m'
	BLUE    = '\033[94m'
	BLUE2   = '\033[1;94m'
	PINK    = '\033[95m'
	PINK2   = '\033[1;95m'
	CYAN    = '\033[96m'
	CYAN2   = '\033[1;96m'
	GRAY    = '\033[1;30m'
	WHITE   = '\033[1;37m'

	BOLD      = '\033[1m'
	UNDERLINE = '\033[4m'

	ENDC   = '\033[0m'
	NORMAL = '\033[0m'

def clr(s, c):
	return "%s%s%s" % (c, s, Color.ENDC)

# Highlight the string pattern in s.
def highlight(s, pattern, c=Color.YELLOW2):
	return s.replace(pattern, clr(pattern, c))

def highlight_match(match):
	txt, pattern = match
	d = highlight(txt, pattern)

	d = d.replace(" \"u", "ü")
	d = d.replace(" \"o", "ö")
	d = d.replace(" \"a", "ä")
	d = d.replace("\"u", "ü")
	d = d.replace("\"o", "ö")
	d = d.replace("\"a", "ä")

	return d

# Search query in pdfs located in directory path.
def search(index, query, path, filenames_only=False):
	rootdir = os.path.abspath(path)
	for fname, file in index["files"].items():
		if not fname.startswith(rootdir):
			continue

		txt = index["hashs"][file["hash"]]
		if isinstance(txt, unicode):
			txt = txt.encode("utf8")

		query2 = query.replace("ü", " \"u")
		query2 = query2.replace("ö", " \"o")
		query2 = query2.replace("ä", " \"a")

		query3 = query.replace("ü", "\"u")
		query3 = query3.replace("ö", "\"o")
		query3 = query3.replace("ä", "\"a")

		# TODO escape query
		matches = re.findall("^(.*(%s|%s|%s).*)$" % (query, query2, query3),
		    txt, re.IGNORECASE | re.MULTILINE)
		if len(matches) == 0:
			continue

		if filenames_only:
			if rootdir == fname:
				print path.encode("utf8")
			else:
				print os.path.relpath(fname, rootdir).encode("utf8")
		else:
			print ""
			print clr(os.path.relpath(fname, rootdir).encode("utf8"), Color.WHITE)
			print "\n".join(map(highlight_match, matches))


if __name__ == '__main__':
	# TODO add option to disable regex
	# TODO add list cache
	# TODO add clear cache
	parser = argparse.ArgumentParser(description='Indexed search in files.')
	parser.add_argument('-l', "--files-with-matches", const=True, default=False,
		dest="filenames_only", action='store_const',
		help='Only print filenames that contain matches')
	parser.add_argument('--no-parse', const=False, default=True, dest="parse_files",
		action='store_const', help='Query only index, don\'t indize any file')
	parser.add_argument('query', help='The string to search for')
	parser.add_argument('directory', nargs='?', help='The directory to search in')

	args = parser.parse_args()

	query = args.query
	path = os.getcwd() if args.directory is None else args.directory
	if not os.path.exists(path):
		print "cannot access '%s': No such file or directory" % path
		exit()

	index = load_index(INDEX_PATH, args.parse_files)
	if args.parse_files:
		if os.path.isdir(path):
			try:
				dir_to_index(index, path, True)
				save_index(INDEX_PATH, index)
			except KeyboardInterrupt:
				exit()
		elif os.path.isfile(path):
			add_file_to_index(index, path)
			save_index(INDEX_PATH, index)

	search(index, query, path, args.filenames_only)
