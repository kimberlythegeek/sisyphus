# -*- Makefile -*-

all: spider.xpi

FILES=$(shell cat ./file.manifest)

spider.xpi: chrome/Makejar $(FILES)
	make -C chrome -f Makejar
	zip -r -o $@ chrome.manifest install.rdf install.js user.js chrome/spider.jar components/
	install $@ ../xpi/all/

clean:
	rm -f spider.xpi


