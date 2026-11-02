# Build the paper. Needs pdflatex and bibtex on PATH.
#
#   make          build main.pdf
#   make check    report page count, undefined refs and bad boxes
#   make clean    remove build artefacts, keep the pdf

TEX := pdflatex -interaction=nonstopmode
MAIN := main

all: $(MAIN).pdf

# Three passes plus bibtex: the first resolves nothing, bibtex builds the
# bibliography, and the last two settle cross-references and the page numbers
# they shift.
$(MAIN).pdf: $(MAIN).tex refs.bib
	$(TEX) $(MAIN) >/dev/null
	bibtex $(MAIN) >/dev/null || true
	$(TEX) $(MAIN) >/dev/null
	$(TEX) $(MAIN) | grep -E "^(!|Output written)" || true

check: $(MAIN).pdf
	@echo "pages:"; grep -oE "Output written on $(MAIN).pdf \([0-9]+ pages?" $(MAIN).log
	@echo "undefined citations: $$(grep -c 'Citation.*undefined' $(MAIN).log || true)"
	@echo "undefined references: $$(grep -c 'Reference.*undefined' $(MAIN).log || true)"
	@echo "TODO / pending in source: $$(grep -cE 'TODO|\\pending\{' $(MAIN).tex || true)"
	@echo "overfull boxes over 10pt:"; \
	  grep -oE "Overfull .hbox \([0-9.]+pt" $(MAIN).log | awk -F'[(]' '$$2+0>10' || true

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).blg $(MAIN).log $(MAIN).out p?.log bib.log

.PHONY: all check clean
