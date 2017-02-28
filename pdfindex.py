#!/usr/bin/env python2
#coding: UTF-8
import subprocess
import os
import zlib
import argparse
import json
import re
import textract


INDEX_PATH = os.path.expanduser("~/.pdfindex")

# Parse a pdf file and returns containing text.
def pdf_to_text(fname):
	# TODO faster alternative?
	return textract.process(fname)
	# return subprocess.check_output(['ps2ascii', fname])

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

	for i,fname in enumerate(file_list):
		print "[%s/%s] %s" % (i+1, len(file_list), fname)
		add_file_to_index(index, fname)

		if instant_save:
			# TODO make atomic
			save_index(INDEX_PATH, index)

	return index

# Returns true, iff the file needs to be updated in index.
def need_update(index, fname):
	if not fname.endswith(".pdf"):
		return False
	fname = os.path.abspath(fname).decode("utf8")

	if not os.path.isfile(fname):
		return False

	if fname in index:
		# TODO check with sha256
		if os.path.getmtime(fname) != index[fname]["modified"]:
			print "modified: %s" % fname
			return True
		else:
			return False
	else:
		return True

# Checks if the given file (fname) needs to be updated in the index
# and, if needed, do this.
def add_file_to_index(index, fname):
	if not fname.endswith(".pdf"):
		return
	fname = os.path.abspath(fname)

	if not os.path.isfile(fname):
		if fname in index:
			del index[fname]
		return

	if fname in index:
		if os.path.getmtime(fname) != index[fname]["modified"]:
			print "modified: %s" % fname
		else:
			return
	else:
		index[fname] = {}

	index[fname]["txt"] = pdf_to_text(fname)
	index[fname]["modified"] = os.path.getmtime(fname)

# saves the index to file
def save_index(fname, index):
	# TODO atomic/backup?
	d = zlib.compress(json.dumps(index))
	open(fname, "wb").write(d)

# loads the index from given file
def load_index(fname, parse_files=False):
	if not os.path.isfile(fname):
		return {}

	d = open(fname, "rb").read()
	index = json.loads(zlib.decompress(d))
	if parse_files:
		for fname in index.keys():
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
	d = highlight(txt.encode("utf8"), pattern.encode("utf8"))

	d = d.replace(" \"u", "ü")
	d = d.replace(" \"o", "ö")
	d = d.replace(" \"a", "ä")
	d = d.replace("\"u", "ü")
	d = d.replace("\"o", "ö")
	d = d.replace("\"a", "ä")

	return d

# Search query in pdfs located in directory path.
def search(index, query, path, filenames_only=False):
	abspath = os.path.abspath(path)
	for fname, d in index.items():
		if not fname.startswith(abspath):
			continue

		query2 = query.replace("ü", " \"u")
		query2 = query2.replace("ö", " \"o")
		query2 = query2.replace("ä", " \"a")

		query3 = query.replace("ü", "\"u")
		query3 = query3.replace("ö", "\"o")
		query3 = query3.replace("ä", "\"a")

		# TODO escape query
		matches = re.findall("^(.*(%s|%s|%s).*)$"%(query,query2,query3), d["txt"], re.IGNORECASE|re.MULTILINE)
		if len(matches) == 0:
			continue

		if filenames_only:
			print fname
		else:
			print ""
			print clr(fname, Color.WHITE)
			print "\n".join(map(highlight_match, matches))


if __name__ == '__main__':
	# TODO add option to disable regex
	parser = argparse.ArgumentParser(description='Indexed search in files.')
	parser.add_argument('-l', "--files-with-matches", const=True, default=False, dest="filenames_only",
		action='store_const', help='Only print filenames that contain matches')
	parser.add_argument('--no-parse', const=False, default=True, dest="parse_files",
		action='store_const', help='Query only index, don\'t indize any file')
	parser.add_argument('query', help='The string to search for')
	parser.add_argument('directory', nargs='?', help='The directory to search in')

	args = parser.parse_args()

	query = args.query
	path = os.getcwd() if args.directory is None else args.directory

	# TODO do this threaded
	index = load_index(INDEX_PATH, args.parse_files)
	if args.parse_files:
		dir_to_index(index, path, True)
		save_index(INDEX_PATH, index)

	search(index, query, path, args.filenames_only)
