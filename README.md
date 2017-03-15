# pdfindex

Builds a compressed and naive index over given pdfs and searches in them.

To get the raw text of a pdf, it have to be parsed.
This can't be done quickly, so it makes sense to index the pdf once, compress it and search in this index structure.
That's where this tool steps in.

The index will be saved at `~/.pdfindex` and is compressed with zlib.
Some more advanced Index structure is planed but not implemented atm.
If you ever move or copy some pdf file, this tool compares the sha256 of the files and it don't have to reparse it.

In german texts there are often umlauts, which we try to fix by using some simple replacements.

A quick comparison between pdfgrep and pdfindex:
| | pdfgrep | pdfindex |
| --- | --- | --- |
|index format | multiple files named by sha1 of the file | one file |
|file recognition | sha1 | filename, modification time, sha256 |
|index compression | No | Yes, zlib |

## Requirements

To parse the pdf files we use `textract`.
```
pip2 install textract
```
The tool is written in Python2.7, so `pyhton2` have to be installed as well.


## Usage

```
./pdfindex.py query [directory|file]
```

If you want to search for `test` in the current directory, just run:
```
./pdfindex.py test
```