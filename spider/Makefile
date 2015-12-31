# -*- Makefile -*-

all: spider.xpi

FILES=$(shell cat ./file.manifest | grep -Ev '\.htaccess|spider.jar')

chrome/spider.jar: $(FILES)
	make -C chrome -f Makejar

spider.xpi: file.manifest chrome/Makejar chrome/spider.jar $(FILES)
	zip -r -o $@ `cat file.manifest`

clean:
	make -C chrome -f Makejar clean
	rm -f spider.xpi



