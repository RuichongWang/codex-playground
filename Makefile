.PHONY: check loc
check: loc
	@python3 check.py
loc:
	@./tools/loc.sh
