# -*- Makefile -*-

all: spider.xpi

FILES=$(shell cat ./file.manifest)

chrome/spider.jar:
	make -C chrome -f Makejar

spider.xpi: file.manifest chrome/Makejar $(FILES)
	zip -r -o $@ `cat file.manifest`
	install $@ ../xpi/all/

clean:
	make -C chrome -f Makejar clean
	rm -f spider.xpi



