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
from copy import deepcopy


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
		t = t.replace("%sĚ" % c, u)
	t = t.replace("Ă", "ß")
	return t

def hash_file(fname):
	d = open(fname, "rb").read()
	return hashlib.sha256(d).hexdigest()

def stderr(s):
	print >> sys.stderr, s

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
		# stderr("[%s/%s] %s" % (i+1, len(file_list), os.path.relpath(fname,rootdir)))
		add_file_to_index(index, fname)

		if instant_save and time() > last_save + 10:
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

	if fname in index["files"] \
	    and os.path.getmtime(fname) == index["files"][fname]["modified"]\
	    and index["files"][fname]["hash"] in index["hashs"]:
		return

	h = hash_file(fname)
	modified = os.path.getmtime(fname)

	if not h in index["hashs"]:
		index["hashs"][h] = pdf_to_text(fname)

	index["files"][fname] = {
		"hash": h,
		"modified": modified
	}


# saves the index to file
def save_index(fname, index):
	if index == orig_data:
		# stderr("index already up-to-date :)")
		return

	d = zlib.compress(json.dumps(index))
	if os.path.exists(fname):
		os.rename(fname, "%s_bak" % fname)
	open(fname, "wb").write(d)
	# stderr("index file saved")

orig_data = None

# loads the index from given file
def load_index(fname, parse_files=False):
	global orig_data
	if not os.path.isfile(fname):
		return {"files": {}, "hashs": {}}

	d = open(fname, "rb").read()
	index = json.loads(zlib.decompress(d))
	orig_data = deepcopy(index)
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

# Iff txt is a unicode, it will encode it as UTF8.
def enc(txt):
	if isinstance(txt, unicode):
		return txt.encode("utf8")
	else:
		return txt


# Search query in pdfs located in directory path.
def search(index, query, path, filenames_only=False):
	rootdir = os.path.abspath(path)
	for fname, file in index["files"].items():
		if not fname.startswith(rootdir):
			continue

		if file["hash"] not in index["hashs"]:
			print "\nERROR Index file corrupt! (missing hash)"
			print fname
			print file
			exit(1)
		txt = index["hashs"][file["hash"]]
		txt = enc(txt)

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
				print enc(os.path.relpath(fname, rootdir))
		else:
			print ""
			print clr(enc(os.path.relpath(fname, rootdir)), Color.WHITE)
			print "\n".join(map(highlight_match, matches))


if __name__ == '__main__':
	# TODO add option to disable regex
	parser = argparse.ArgumentParser(description='Indexed search in files.')
	parser.add_argument('-l', "--files-with-matches", const=True, default=False,
		dest="filenames_only", action='store_const',
		help='Only print filenames that contain matches')
	parser.add_argument('--no-parse', const=False, default=True, dest="parse_files",
		action='store_const', help='Query only index, don\'t indize any file')
	parser.add_argument('query', nargs="?", default=None, help='The string to search for')
	parser.add_argument('directory', nargs='?', help='The directory to search in')

	group = parser.add_mutually_exclusive_group()
	group.add_argument('--cached-files', const=True, default=False,
		dest="cached_files", action="store_const", help="List all cached files")
	group.add_argument('--cached-hashs', const=True, default=False,
		dest="cached_hashs", action="store_const", help="List all cached hashs")

	parser.add_argument('--clear-cache', const=True, default=False, dest="clear_cache",
		action='store_const', help='Clear cache')

	args = parser.parse_args()

	if args.clear_cache:
		os.remove(INDEX_PATH)
		exit()

	if args.cached_files:
		index = load_index(INDEX_PATH)
		for f in index["files"]:
			print f.encode("utf8")
		exit()

	if args.cached_hashs:
		index = load_index(INDEX_PATH)
		for h in index["hashs"]:
			print h
		exit()

	if args.query is None:
		parser.print_usage()
		print "%s: error: too few arguments" % os.path.split(sys.argv[0])[1]
		exit(2)

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
				save_index(INDEX_PATH, index)
				exit()
		elif os.path.isfile(path):
			add_file_to_index(index, path)
			save_index(INDEX_PATH, index)

	search(index, query, path, args.filenames_only)
